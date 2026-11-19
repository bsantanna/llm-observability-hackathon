"""Shared setup and activity helpers for the LLM Observability Hackathon.

The notebooks call these functions and focus on the activity logs. Importing
this module validates the environment, creates the clients, loads the sample
data, and exposes the trace helpers.
"""

import json
import os
import re
import time
import uuid
from pathlib import Path

from langfuse import Langfuse, propagate_attributes
from langfuse.openai import OpenAI

from game import check_flag, current_team, hint, open_door, set_team

REQUIRED = [
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
    "OPENAI_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
]
missing = [name for name in REQUIRED if not os.environ.get(name)]
if missing:
    raise RuntimeError("Missing environment variables: " + ", ".join(missing))

LANGFUSE_BASE_URL = os.environ["LANGFUSE_BASE_URL"]
MODEL = os.environ["OPENAI_MODEL"]
RUN_ID = uuid.uuid4().hex[:8]
TRACE_URLS = {}

langfuse = Langfuse()
try:
    authenticated = langfuse.auth_check()
except Exception as exc:
    raise RuntimeError(
        f"Langfuse authentication failed for {LANGFUSE_BASE_URL}: {exc}"
    ) from exc
if not authenticated:
    raise RuntimeError(f"Langfuse authentication failed for {LANGFUSE_BASE_URL}")

client = OpenAI(
    base_url=os.environ["OPENAI_BASE_URL"],
    api_key=os.environ["OPENAI_API_KEY"],
)

_CORPUS_PATH = Path(__file__).resolve().parent / "data" / "travel_corpus.json"
with _CORPUS_PATH.open(encoding="utf-8") as _corpus_file:
    CORPUS = json.load(_corpus_file)

BOOKINGS = CORPUS["bookings"]
REQUESTS = CORPUS["requests"]
INSTRUCTIONS = CORPUS["instructions"]
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_booking",
        "description": "Look up a booking by reference",
        "parameters": {
            "type": "object",
            "properties": {"booking_ref": {"type": "string"}},
            "required": ["booking_ref"],
        },
    },
}


def trace_url(trace_id):
    url = langfuse.get_trace_url(trace_id=trace_id) or trace_id
    return url.replace("://langfuse:3000", "://localhost:3000")


def show_trace(trace_id):
    url = trace_url(trace_id)
    print(f"activity log: {url}")
    return url


def record_trace(name, trace_id):
    url = trace_url(trace_id)
    TRACE_URLS[name] = url
    return url


def print_summary(activity):
    print(f"session activity-{activity}-{RUN_ID}")
    for name, url in TRACE_URLS.items():
        print(f"{name}: {url}")


LOG_QUERY = "bag found on board"


def _rank(query, records, top_k):
    """Keyword search: score = how many query words appear in the text; ties keep file order."""
    terms = re.findall(r"[a-z0-9]+", query.lower())
    ranked = sorted(
        ((sum(term in record["text"].lower() for term in terms), index, record)
         for index, record in enumerate(records)),
        key=lambda row: (-row[0], row[1]),
    )
    return [{**record, "score": score} for score, _, record in ranked[:top_k]]


def search_log(query, flight=None, *, top_k=1):
    """Search the lost-and-found log, optionally only one flight's items."""
    entries = CORPUS["lost_and_found"]
    if flight is not None:
        entries = [entry for entry in entries if entry["flight"] == flight]
    return _rank(query, entries, top_k)


BOOKING_FIELDS = ("origin", "destination", "travel_date", "passengers", "cabin")
STRUCTURED_INSTRUCTIONS = (
    "Return ONLY a JSON object with exactly these keys: origin, destination, travel_date, "
    "passengers, cabin. travel_date must be YYYY-MM-DD; passengers must be an integer; "
    "cabin must be economy or premium. No prose and no markdown fences."
)
CLARIFICATION_EXPECTED = {2: "travel_date", 3: "cabin"}


def validate_booking_request(text, *, allow_clarification=False):
    """Return (valid, parsed, reason, reason_code) for the booking system's contract."""
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return False, None, "the answer is not a structured object", "NOT_AN_OBJECT"
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return False, None, "the structured answer could not be read", "UNREADABLE"
    if not isinstance(parsed, dict):
        return False, parsed, "the answer must be a structured object", "NOT_AN_OBJECT"
    if allow_clarification and set(parsed) == {"needs_clarification"}:
        if parsed["needs_clarification"] in BOOKING_FIELDS:
            return True, parsed, "the assistant asks for a missing detail", "CLARIFICATION"
        return False, parsed, "needs_clarification must name one booking field", "WRONG_FIELDS"
    if set(parsed) != set(BOOKING_FIELDS):
        return False, parsed, (
            "the answer must contain exactly these fields: origin, destination, "
            "travel date, passengers, cabin"
        ), "WRONG_FIELDS"
    if not isinstance(parsed["origin"], str) or not parsed["origin"]:
        return False, parsed, "the origin is missing or empty", "MISSING_ORIGIN"
    if not isinstance(parsed["destination"], str) or not parsed["destination"]:
        return False, parsed, "the destination is missing or empty", "MISSING_DESTINATION"
    if not isinstance(parsed["travel_date"], str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", parsed["travel_date"]
    ):
        return False, parsed, "the travel date must use YYYY-MM-DD", "BAD_DATE"
    if not isinstance(parsed["passengers"], int) or isinstance(parsed["passengers"], bool):
        return False, parsed, "the number of passengers must be a whole number", "BAD_PASSENGERS"
    if parsed["cabin"] not in {"economy", "premium"}:
        return False, parsed, "the cabin must be economy or premium", "BAD_CABIN"
    return True, parsed, "all fields present and correct", "OK"


def batch_passes(number, valid, parsed, reason_code):
    """Clue 2-3 rule: requests 2 and 3 must ask for the right missing detail, request 1 must book."""
    if not valid:
        return False
    if number in CLARIFICATION_EXPECTED:
        return reason_code == "CLARIFICATION" and parsed["needs_clarification"] == CLARIFICATION_EXPECTED[number]
    return reason_code == "OK"


def activity_tags(activity, level, variant):
    tags = [f"activity-{activity}", f"l{level}", variant]
    if current_team():
        tags.append(f"team-{current_team()}")
    return tags


def run_rag(customer_message, flight, variant, *, level=1, query=LOG_QUERY, top_k=1, send_all=False):
    trace_name = f"activity-1-rag-l{level}-{variant}"
    if send_all:
        label = "the whole log sent"
        items = search_log(query, top_k=len(CORPUS["lost_and_found"]))
        search_filter = None
    else:
        label = "every flight" if flight is None else f"flight {flight} only"
        if top_k > 1:
            label += f", top {top_k} results"
        items = search_log(query, flight, top_k=top_k)
        search_filter = {"flight": flight} if flight else None
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(
            session_id=f"activity-1-{RUN_ID}",
            tags=activity_tags(1, level, variant),
            trace_name=trace_name,
        ):
            with langfuse.start_as_current_observation(
                name="activity-1-retrieval",
                as_type="retriever",
                input={"query": query, "filter": search_filter, "top_k": len(items) if send_all else top_k},
                output={"count": len(items),
                        "items": [{key: item[key] for key in ("id", "flight", "item", "text")} for item in items]},
                metadata={"detective_note": "golden-fishhook"},
            ):
                pass
            entries = "\n".join(f"- {item['text']}" for item in items)
            messages = [
                {"role": "system", "content": "You are Skye, Skyline Travel's assistant. The search returns the items found for this customer: tell them cheerfully what we found for them, using the lost-and-found entries."},
                {"role": "user", "content": f"{customer_message}\n\nLost-and-found entries:\n{entries}"},
            ]
            started = time.time()
            response = client.chat.completions.create(
                model=MODEL, messages=messages, temperature=0, max_tokens=800,
                name="activity-1-generation",
            )
            latency = time.time() - started
            answer = response.choices[0].message.content
            trace_id = langfuse.get_current_trace_id()
            root.update(output={"answer": answer})
    usage = response.usage
    return {
        "variant": variant,
        "level": level,
        "label": label,
        "answer": answer,
        "items": items,
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "latency": latency,
        "trace_id": trace_id,
        "trace_url": record_trace(f"activity-1-l{level}-{variant}", trace_id),
    }


def _ask(system, request, name):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": request}]
    started = time.time()
    response = client.chat.completions.create(
        model=MODEL, messages=messages, temperature=0, max_tokens=300, name=name,
    )
    return response, time.time() - started


def run_format(variant):
    trace_name = f"activity-2-output-l1-{variant}"
    label = "free text" if variant == "unconstrained" else "structured"
    system = (
        "Summarize the customer's booking request in one sentence."
        if variant == "unconstrained"
        else STRUCTURED_INSTRUCTIONS
    )
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(
            session_id=f"activity-2-{RUN_ID}",
            tags=activity_tags(2, 1, variant),
            trace_name=trace_name,
        ):
            response, latency = _ask(system, REQUESTS[0], "activity-2-generation")
            answer = response.choices[0].message.content
            valid, parsed, reason, reason_code = validate_booking_request(answer)
            trace_id = langfuse.get_current_trace_id()
            root.update(output={"valid": valid, "reason": reason, "reason_code": reason_code, "parsed": parsed})
    usage = response.usage
    return {
        "variant": variant,
        "level": 1,
        "label": label,
        "answer": answer,
        "valid": valid,
        "parsed": parsed,
        "reason": reason,
        "reason_code": reason_code,
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "latency": latency,
        "trace_id": trace_id,
        "trace_url": record_trace(f"activity-2-l1-{variant}", trace_id),
    }


def run_format_batch(instructions, level):
    trace_name = f"activity-2-output-l{level}-batch"
    allow_clarification = level >= 3
    results = []
    with langfuse.start_as_current_observation(
        name=trace_name, as_type="span", input={"instructions": instructions}
    ) as root:
        with propagate_attributes(
            session_id=f"activity-2-{RUN_ID}",
            tags=activity_tags(2, level, "batch"),
            trace_name=trace_name,
        ):
            for number, request in enumerate(REQUESTS, start=1):
                with langfuse.start_as_current_observation(
                    name=f"request-{number}", as_type="span", input={"request": request}
                ) as step:
                    response, _ = _ask(instructions, request, "activity-2-generation")
                    answer = response.choices[0].message.content
                    valid, parsed, reason, reason_code = validate_booking_request(
                        answer, allow_clarification=allow_clarification
                    )
                    usable = batch_passes(number, valid, parsed, reason_code) if allow_clarification else valid
                    step.update(output={"request": request, "valid": valid, "reason_code": reason_code,
                                        "reason": reason, "parsed": parsed, "usable": usable})
                results.append({"number": number, "request": request, "answer": answer, "usable": usable})
            passed = sum(result["usable"] for result in results)
            trace_id = langfuse.get_current_trace_id()
            root.update(output={"usable": passed, "of": len(results)})
    return {
        "variant": "batch",
        "level": level,
        "label": f"{len(results)} requests, {passed} usable",
        "passed": passed,
        "results": results,
        "trace_id": trace_id,
        "trace_url": record_trace(f"activity-2-l{level}-batch", trace_id),
    }


NOTICE_QUERY = "rooster bird cabin seat"
FARMER_QUESTION = (
    "Farmer Barnaby here. I am flying with Sir Crowsalot, my rooster, so he can wake me at dawn "
    "when we land. Can he sit with me in the cabin?"
)
FAITHFUL_INSTRUCTIONS = (
    "You are Skye, Skyline Travel's assistant. Answer using only the retrieved notice. "
    "If it conflicts with your assumptions, follow the notice."
)
RULE_QUESTIONS = [
    ("where", "Where on the plane will my rooster travel? He is a very good boy.", "rooster travel cabin hold fee"),
    ("fee", "What do I pay to bring my rooster along?", "rooster travel cabin hold fee"),
]


def search_notices(query, *, top_k=1, active_only=True):
    """Search the animals-on-board and other notices, by default only the current ones."""
    notices = CORPUS["notices"]
    if active_only:
        notices = [notice for notice in notices if notice["status"] == "active"]
    return _rank(query, notices, top_k)


def rule_passes(topic, answer):
    text = (answer or "").lower()
    if topic == "where":
        return bool(re.search(r"\b(hold|cargo)\b", text))
    if topic == "fee":
        return bool(re.search(r"\b80\b", text))
    raise ValueError(f"unknown topic {topic}")


def _notice_answer(system_prompt, question, query, active_only, step_name, *, top_k=1, show_status=False):
    docs = search_notices(query, top_k=top_k, active_only=active_only)
    doc = docs[0]
    with langfuse.start_as_current_observation(
        name="activity-3-retrieval",
        as_type="retriever",
        input={"query": query, "filter": {"active_only": active_only}, "top_k": top_k},
        output={"doc_id": doc["id"], "status": doc["status"], "effective_to": doc["effective_to"],
                "title": doc["title"], "text": doc["text"],
                "docs": [{key: item[key] for key in ("id", "status", "effective_to", "text")} for item in docs]},
    ):
        pass
    if show_status:
        policies = "\n".join(
            f"- [status: {item['status']}"
            + (f", valid until {item['effective_to']}" if item["effective_to"] else "")
            + f"] {item['text']}"
            for item in docs
        )
    else:
        policies = "\n".join(item["text"] for item in docs)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{question}\n\nRetrieved notice:\n{policies}"},
    ]
    started = time.time()
    response = client.chat.completions.create(
        model=MODEL, messages=messages, temperature=0, max_tokens=800, name=step_name,
    )
    return doc, response, time.time() - started


def run_hallucination(system_prompt, variant, *, level=1, active_only=True):
    if system_prompt is None:
        system_prompt = INSTRUCTIONS["case-3-broken"]
    trace_name = f"activity-3-hallucination-l{level}-{variant}"
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(
            session_id=f"activity-3-{RUN_ID}",
            tags=activity_tags(3, level, variant),
            trace_name=trace_name,
        ):
            doc, response, latency = _notice_answer(
                system_prompt, FARMER_QUESTION, NOTICE_QUERY, active_only, "activity-3-generation"
            )
            answer = response.choices[0].message.content
            trace_id = langfuse.get_current_trace_id()
            root.update(output={"answer": answer})
    usage = response.usage
    return {
        "variant": variant,
        "level": level,
        "label": variant,
        "answer": answer,
        "doc": doc,
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "latency": latency,
        "trace_id": trace_id,
        "trace_url": record_trace(f"activity-3-l{level}-{variant}", trace_id),
    }


def run_rule_check(system_prompt):
    """The base instructions from Level 1 are always sent first; the team's instructions follow."""
    trace_name = "activity-3-hallucination-l3-rules"
    instructions = INSTRUCTIONS["case-3-broken"] + "\n\n" + system_prompt
    results = []
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(
            session_id=f"activity-3-{RUN_ID}",
            tags=activity_tags(3, 3, "rules"),
            trace_name=trace_name,
        ):
            for topic, question, query in RULE_QUESTIONS:
                with langfuse.start_as_current_observation(
                    name=f"rule-check-{topic}", as_type="span", input={"question": question}
                ) as step:
                    _, response, _ = _notice_answer(
                        instructions, question, query, False, "activity-3-generation", top_k=2, show_status=True
                    )
                    answer = response.choices[0].message.content
                    passed = rule_passes(topic, answer)
                    step.update(output={"answer": answer, "matches_notice": passed})
                results.append({"topic": topic, "question": question, "answer": answer, "passed": passed})
            passed = sum(result["passed"] for result in results)
            trace_id = langfuse.get_current_trace_id()
            root.update(output={"matches_notice": passed, "of": len(results)})
    return {
        "variant": "rules",
        "level": 3,
        "label": f"rule check, {passed} of {len(results)} match the notice",
        "passed": passed,
        "results": results,
        "trace_id": trace_id,
        "trace_url": record_trace("activity-3-l3-rules", trace_id),
    }


def get_booking_l1(**kwargs):
    ref = kwargs["booking_id"]
    return BOOKINGS[ref]


def get_booking_l2(**kwargs):
    """Accepts any spelling of the reference and never fails."""
    key = kwargs["booking_ref"].upper().replace("-", "")
    booking = BOOKINGS.get(key)
    if booking is None:
        key, booking = next(iter(BOOKINGS.items()))
    return {"booking_ref": key, **booking}


PARTNER_CACHE = {ref: "verified" for ref in BOOKINGS}
PARTNER_WAIT_SECONDS = 1.5
PARTNER_ATTEMPTS = 3


def make_partner_lookup(cache_key):
    """Lookup that double-checks the booking with the piano movers' system, using a cache of verified bookings.

    On a cache miss the tool waits for the slow piano movers' system and checks again, up to three times.
    """
    def get_booking(**kwargs):
        ref = kwargs["booking_ref"]
        for attempt in range(1, PARTNER_ATTEMPTS + 1):
            key = cache_key(ref)
            with langfuse.start_as_current_observation(
                name="piano-mover-check", as_type="span", input={"booking_ref": ref, "attempt": attempt}
            ) as step:
                if key in PARTNER_CACHE:
                    step.update(output={"cache": "hit"})
                    break
                time.sleep(PARTNER_WAIT_SECONDS)
                step.update(output={"cache": "miss", "piano_movers": "no answer yet, they are lifting something"})
        return {"booking_ref": ref, **BOOKINGS[ref]}
    return get_booking


def run_tool_loop(question, variant, *, level=1, lookup):
    trace_name = f"activity-4-tool-call-l{level}-{variant}"
    tool_args = None
    tool_result = None
    answer = None
    started = time.time()
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(
            session_id=f"activity-4-{RUN_ID}",
            tags=activity_tags(4, level, variant),
            trace_name=trace_name,
        ):
            messages = [
                {"role": "system", "content": "You are Skye, Skyline Travel's assistant. Use the get_booking tool to look up bookings and their checked items. If a tool call fails, apologise and ask the customer to try again later, without retrying and without showing technical details or error messages. Do not repeat booking references back to the customer; describe the trip instead."},
                {"role": "user", "content": question},
            ]
            first = client.chat.completions.create(
                model=MODEL, messages=messages, tools=[TOOL_SCHEMA], tool_choice="required",
                temperature=0, max_tokens=800, name="activity-4-generation-1",
            )
            message = first.choices[0].message
            if message.tool_calls:
                messages.append(message.model_dump(exclude_none=True))
                for call in message.tool_calls:
                    args = json.loads(call.function.arguments)
                    with langfuse.start_as_current_observation(
                        name="get_booking", as_type="tool", input=args
                    ) as tool_span:
                        try:
                            result = lookup(**args)
                            tool_span.update(output=result)
                        except Exception as exc:
                            result = {"error": f"{type(exc).__name__}: {exc}"}
                            tool_span.update(
                                level="ERROR",
                                status_message=f"{type(exc).__name__}: {exc}",
                                output=result,
                            )
                    if tool_args is None:
                        tool_args, tool_result = args, result
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
                second = client.chat.completions.create(
                    model=MODEL, messages=messages, tools=[TOOL_SCHEMA], tool_choice="auto",
                    temperature=0, max_tokens=800, name="activity-4-generation-2",
                )
                answer = second.choices[0].message.content
            else:
                answer = message.content
            trace_id = langfuse.get_current_trace_id()
            root.update(output={"answer": answer})
    return {
        "variant": variant,
        "level": level,
        "label": variant,
        "answer": answer,
        "tool_args": tool_args,
        "tool_result": tool_result,
        "latency": time.time() - started,
        "trace_id": trace_id,
        "trace_url": record_trace(f"activity-4-l{level}-{variant}", trace_id),
    }


def show_rag_results(runs):
    for run in runs:
        print(f"\n🔎 {run['label']}")
        print(f"  answer: {run['answer']}")
        print(f"  tokens: {run['input_tokens']} in / {run['output_tokens']} out · latency: {run['latency']:.1f}s")
        print(f"  activity log: {run['trace_url']}")


def show_format_results(runs):
    for run in runs:
        print(f"\n▶ {run['label']}")
        print(f"  answer: {run['answer']}")
        print(f"  booking system: {'ACCEPTED' if run['valid'] else 'REJECTED'} — {run['reason']}")
        print(f"  tokens: {run['input_tokens']} in / {run['output_tokens']} out · latency: {run['latency']:.1f}s")
        print(f"  activity log: {run['trace_url']}")


def show_batch_results(batch):
    print(f"\n📨 {batch['passed']} of {len(batch['results'])} answers usable")
    for result in batch["results"]:
        print(f"  {'✅' if result['usable'] else '❌'} request {result['number']}: {result['request']}")
    print(f"  activity log: {batch['trace_url']}")
    if batch["level"] >= 3 and batch["passed"] == len(batch["results"]):
        print("\n🏆 All three usable. Flag: three-for-three")


def show_hallucination_results(runs):
    for run in runs:
        print(f"\n▶ {run['label']}")
        print(f"  answer: {run['answer']}")
        print(f"  activity log: {run['trace_url']}")


def show_rule_results(check):
    print(f"\n🐓 {check['passed']} of {len(check['results'])} answers match the notice")
    for result in check["results"]:
        print(f"  {'✅' if result['passed'] else '❌'} {result['question']}")
        print(f"     {result['answer']}")
    print(f"  activity log: {check['trace_url']}")
    if check["passed"] == len(check["results"]):
        print("\n🏆 Skye said no to the rooster. Flag: quiet-flight")


def show_tool_results(runs):
    for run in runs:
        print(f"\n▶ {run['label']}")
        print(f"  answer: {run['answer']}")
        print(f"  latency: {run['latency']:.1f}s")
        print(f"  activity log: {run['trace_url']}")


def close_case(activity, runs):
    print(f"\ncase {activity} closed — session {activity}-{RUN_ID}")
    for run in runs:
        print(f"{run['label']}: {run['trace_url']}")
    langfuse.flush()
    print("activity logs flushed to Langfuse")
