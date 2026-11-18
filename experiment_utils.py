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

from game import check_flag, current_team, hint, set_team

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


def retrieve(query, tier=None, *, topic=None, top_k=1, active_only=True):
    documents = CORPUS["documents"]
    if tier is not None:
        documents = [doc for doc in documents if doc["tier"] == tier]
    if topic is not None:
        documents = [doc for doc in documents if doc["topic"] == topic]
    if active_only:
        documents = [doc for doc in documents if doc["status"] == "active"]
    terms = re.findall(r"[a-z0-9]+", query.lower())
    ranked = sorted(
        ((sum(term in doc["text"].lower() for term in terms), index, doc)
         for index, doc in enumerate(documents)),
        key=lambda row: (-row[0], row[1]),
    )
    return [
        {
            "id": doc["id"],
            "tier": doc["tier"],
            "topic": doc["topic"],
            "status": doc["status"],
            "effective_to": doc["effective_to"],
            "title": doc["title"],
            "text": doc["text"],
            "score": score,
        }
        for score, _, doc in ranked[:top_k]
    ]


BOOKING_FIELDS = ("origin", "destination", "travel_date", "passengers", "cabin")
STRUCTURED_INSTRUCTIONS = (
    "Return ONLY a JSON object with exactly these keys: origin, destination, travel_date, "
    "passengers, cabin. travel_date must be YYYY-MM-DD; passengers must be an integer; "
    "cabin must be economy or premium. No prose and no markdown fences."
)
CLARIFICATION_EXPECTED = {2: "travel_date", 3: "cabin", 4: "origin"}


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
    """Level 3 rule: requests 2-4 must ask for the right missing detail, 1 and 5 must book."""
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


def run_rag(customer_message, tier, variant, *, level=1, query="checked bag allowance",
            topic=None, top_k=1, send_all=False):
    trace_name = f"activity-1-rag-l{level}-{variant}"
    if send_all:
        label = "every policy sent"
        docs = retrieve(query, top_k=len(CORPUS["documents"]), active_only=False)
        search_filter = None
    else:
        label = "all policies" if tier is None else f"{tier.title()} fare only"
        if top_k > 1:
            label += f", top {top_k} results"
        docs = retrieve(query, tier, topic=topic, top_k=top_k)
        search_filter = {key: value for key, value in (("tier", tier), ("topic", topic)) if value} or None
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(
            session_id=f"activity-1-{RUN_ID}",
            tags=activity_tags(1, level, variant),
            trace_name=trace_name,
        ):
            with langfuse.start_as_current_observation(
                name="activity-1-retrieval",
                as_type="retriever",
                input={"query": query, "filter": search_filter, "top_k": len(docs) if send_all else top_k},
                output={"count": len(docs),
                        "docs": [{key: doc[key] for key in ("id", "tier", "topic", "text")} for doc in docs]},
                metadata={"detective_note": "golden-suitcase"},
            ):
                pass
            policies = "\n".join(f"- {doc['text']}" for doc in docs)
            messages = [
                {"role": "system", "content": "Answer using the retrieved policy documents."},
                {"role": "user", "content": f"{customer_message}\n\nRetrieved policies:\n{policies}"},
            ]
            started = time.time()
            response = client.chat.completions.create(
                model=MODEL, messages=messages, temperature=0, max_tokens=300,
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
        "docs": docs,
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
        "label": f"five requests, {passed} usable",
        "passed": passed,
        "results": results,
        "trace_id": trace_id,
        "trace_url": record_trace(f"activity-2-l{level}-batch", trace_id),
    }


FAITHFUL_INSTRUCTIONS = (
    "You are Skyline Travel's assistant. Answer using only the retrieved policy documents. "
    "If they conflict with your assumptions, follow the documents."
)
RULE_QUESTIONS = [
    ("bags", "How many checked bags are included in my Gold fare?", "checked bag allowance"),
    ("second-bag", "What does a second checked bag cost on my Gold fare?", "second checked bag cost"),
    ("cancellation", "Until when can I cancel my Gold ticket free of charge?", "cancelled free charge hours"),
]


def rule_passes(topic, answer):
    text = (answer or "").lower()
    if topic == "bags":
        return bool(re.search(r"\b(one|1)\b", text)) and not re.search(r"\b(two|2)\b", text)
    if topic == "second-bag":
        return bool(re.search(r"\b60\b", text))
    if topic == "cancellation":
        return bool(re.search(r"\b24\b", text))
    raise ValueError(f"unknown topic {topic}")


def _policy_answer(system_prompt, question, query, active_only, step_name):
    doc = retrieve(query, "gold", active_only=active_only)[0]
    with langfuse.start_as_current_observation(
        name="activity-3-retrieval",
        as_type="retriever",
        input={"query": query, "filter": {"tier": "gold", "active_only": active_only}},
        output={"doc_id": doc["id"], "status": doc["status"], "effective_to": doc["effective_to"],
                "tier": doc["tier"], "text": doc["text"]},
    ):
        pass
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"I'm a Gold member. {question}\n\nRetrieved policy:\n{doc['text']}"},
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
            doc, response, latency = _policy_answer(
                system_prompt, RULE_QUESTIONS[0][1], RULE_QUESTIONS[0][2], active_only, "activity-3-generation"
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
    trace_name = "activity-3-hallucination-l3-rules"
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
                    _, response, _ = _policy_answer(system_prompt, question, query, True, "activity-3-generation")
                    answer = response.choices[0].message.content
                    passed = rule_passes(topic, answer)
                    step.update(output={"answer": answer, "matches_policy": passed})
                results.append({"topic": topic, "question": question, "answer": answer, "passed": passed})
            passed = sum(result["passed"] for result in results)
            trace_id = langfuse.get_current_trace_id()
            root.update(output={"matches_policy": passed, "of": len(results)})
    return {
        "variant": "rules",
        "level": 3,
        "label": f"rule check, {passed} of {len(results)} match the policy",
        "passed": passed,
        "results": results,
        "trace_id": trace_id,
        "trace_url": record_trace("activity-3-l3-rules", trace_id),
    }


def get_booking_broken(**kwargs):
    ref = kwargs["booking_id"]
    return BOOKINGS[ref]


def get_booking_fixed(**kwargs):
    ref = kwargs["booking_ref"]
    return BOOKINGS[ref]


def run_tool_loop(question, variant):
    trace_name = f"activity-4-tool-call-{variant}"
    label = "before fix" if variant == "broken" else "after fix"
    lookup = get_booking_broken if variant == "broken" else get_booking_fixed
    tool_args = None
    tool_result = None
    answer = None
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(
            session_id=f"activity-4-{RUN_ID}",
            tags=["activity-4", variant],
            trace_name=trace_name,
        ):
            messages = [
                {"role": "system", "content": "You are Skyline Travel's assistant. Use the get_booking tool to look up bookings. If a tool call fails, report the failure to the user instead of retrying."},
                {"role": "user", "content": question},
            ]
            first = client.chat.completions.create(
                model=MODEL, messages=messages, tools=[TOOL_SCHEMA], tool_choice="auto",
                temperature=0, max_tokens=800, name="activity-4-generation-1",
            )
            message = first.choices[0].message
            if message.tool_calls:
                call = message.tool_calls[0]
                tool_args = json.loads(call.function.arguments)
                messages.append(message.model_dump(exclude_none=True))
                with langfuse.start_as_current_observation(
                    name="get_booking", as_type="tool", input=tool_args
                ) as tool_span:
                    try:
                        tool_result = lookup(**tool_args)
                        tool_span.update(output=tool_result)
                    except Exception as exc:
                        tool_result = {"error": f"{type(exc).__name__}: {exc}"}
                        tool_span.update(
                            level="ERROR",
                            status_message=f"{type(exc).__name__}: {exc}",
                            output=tool_result,
                        )
                messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(tool_result)})
                second = client.chat.completions.create(
                    model=MODEL, messages=messages, tools=[TOOL_SCHEMA], tool_choice="auto",
                    temperature=0, max_tokens=800, name="activity-4-generation-2",
                )
                answer = second.choices[0].message.content
            else:
                answer = message.content
            trace_id = langfuse.get_current_trace_id()
            root.update(output={"answer": answer, "tool_args": tool_args, "tool_result": tool_result})
    return {
        "variant": variant,
        "label": label,
        "answer": answer,
        "tool_args": tool_args,
        "tool_result": tool_result,
        "trace_id": trace_id,
        "trace_url": record_trace(f"activity-4-{variant}", trace_id),
    }


def show_rag_results(runs):
    for run in runs:
        print(f"\nlevel {run['level']} · {run['label']}")
        print(f"  answer: {run['answer']}")
        print(f"  tokens: {run['input_tokens']} in / {run['output_tokens']} out · latency: {run['latency']:.1f}s")
        print(f"  activity log: {run['trace_url']}")


def show_format_results(runs):
    for run in runs:
        print(f"\nlevel {run['level']} · {run['label']}")
        print(f"  answer: {run['answer']}")
        print(f"  booking system: {'ACCEPTED' if run['valid'] else 'REJECTED'} — {run['reason']}")
        print(f"  tokens: {run['input_tokens']} in / {run['output_tokens']} out · latency: {run['latency']:.1f}s")
        print(f"  activity log: {run['trace_url']}")


def show_batch_results(batch):
    print(f"\nlevel {batch['level']} · {batch['passed']} of {len(batch['results'])} answers usable")
    for result in batch["results"]:
        print(f"  {'✅' if result['usable'] else '❌'} request {result['number']}: {result['request']}")
    print(f"  activity log: {batch['trace_url']}")
    if batch["level"] >= 3 and batch["passed"] == len(batch["results"]):
        print("\n🏆 All five usable. Flag: five-for-five")


def show_hallucination_results(runs):
    for run in runs:
        print(f"\nlevel {run['level']} · {run['label']}")
        print(f"  answer: {run['answer']}")
        print(f"  activity log: {run['trace_url']}")


def show_rule_results(check):
    print(f"\nlevel {check['level']} · {check['passed']} of {len(check['results'])} answers match the policy")
    for result in check["results"]:
        print(f"  {'✅' if result['passed'] else '❌'} {result['question']}")
        print(f"     {result['answer']}")
    print(f"  activity log: {check['trace_url']}")
    if check["passed"] == len(check["results"]):
        print("\n🏆 Every answer matches the policy. Flag: rule-writer")


def show_tool_broken(run):
    print(f"\n{run['label']}")
    print(f"  tool input: {run['tool_args']}")
    print(f"  tool result: {run['tool_result']}")
    print(f"  answer: {run['answer']}")
    print(f"  activity log: {run['trace_url']}")


def show_tool_fixed(broken, fixed):
    for run in (broken, fixed):
        print(f"\n{run['label']}")
        print(f"  tool input: {run['tool_args']}")
        print(f"  tool result: {run['tool_result']}")
        print(f"  answer: {run['answer']}")
        print(f"  activity log: {run['trace_url']}")


def close_case(activity, runs):
    print(f"\ncase {activity} closed — session {activity}-{RUN_ID}")
    for run in runs:
        print(f"level {run.get('level', 1)} · {run['label']}: {run['trace_url']}")
    langfuse.flush()
    print("activity logs flushed to Langfuse")


QUIZZES = {
    "activity-1": {
        "question": "In the filtered run, what filter does the retrieval step record?",
        "options": [
            "No filter — every policy was searched",
            "tier=basic",
            "tier=gold",
            "topic=baggage",
        ],
        "answer": 2,
    },
    "activity-2": {
        "question": "In the constrained run, which field is listed in the generation's system prompt?",
        "options": [
            "origin",
            "booking_ref",
            "loyalty_id",
            "passenger_name",
        ],
        "answer": 1,
    },
    "activity-3": {
        "question": "In the broken run, how many checked bags does the retrieved Gold policy allow?",
        "options": ["one", "two", "three", "unlimited"],
        "answer": 1,
    },
    "activity-4": {
        "question": "In the broken run, what status message does the get_booking tool step record?",
        "options": [
            "KeyError: 'booking_id'",
            "ValueError: booking not found",
            "404 Not Found",
            "No error — the lookup succeeded",
        ],
        "answer": 1,
    },
}


def start_quiz(activity):
    quiz = QUIZZES[activity]
    print(f"optional final check — {activity}")
    print(quiz["question"])
    for number, option in enumerate(quiz["options"], start=1):
        print(f"  {number}. {option}")
    print("set answer to 1, 2, 3, or 4 in the next cell and run it once.")


def submit_quiz(activity, answer):
    quiz = QUIZZES[activity]
    if not isinstance(answer, int) or isinstance(answer, bool) or answer not in (1, 2, 3, 4):
        print("no answer selected yet — set answer to 1, 2, 3, or 4 and run this cell again.")
        return 0
    if answer == quiz["answer"]:
        print(f"correct — 100 points for {activity} (maximum across four cases: 400).")
        return 100
    print(
        f"not correct — 0 points for {activity}. "
        f"Correct option: {quiz['answer']}. {quiz['options'][quiz['answer'] - 1]}"
    )
    return 0
