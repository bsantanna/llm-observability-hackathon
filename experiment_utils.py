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


def validate_booking_request(text):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return False, None, "the answer is not a structured object"
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return False, None, "the structured answer could not be read"
    if not isinstance(parsed, dict):
        return False, parsed, "the answer must be a structured object"
    required = {"origin", "destination", "travel_date", "passengers", "cabin"}
    if set(parsed) != required:
        return False, parsed, (
            "the answer must contain exactly these fields: origin, destination, "
            "travel date, passengers, cabin"
        )
    if not isinstance(parsed["origin"], str) or not parsed["origin"]:
        return False, parsed, "the origin is missing or empty"
    if not isinstance(parsed["destination"], str) or not parsed["destination"]:
        return False, parsed, "the destination is missing or empty"
    if not isinstance(parsed["travel_date"], str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", parsed["travel_date"]
    ):
        return False, parsed, "the travel date must use YYYY-MM-DD"
    if not isinstance(parsed["passengers"], int) or isinstance(parsed["passengers"], bool):
        return False, parsed, "the number of passengers must be a whole number"
    if parsed["cabin"] not in {"economy", "premium"}:
        return False, parsed, "the cabin must be economy or premium"
    return True, parsed, "all fields present and correct"


def run_rag(customer_message, tier, variant):
    trace_name = f"activity-1-rag-{variant}"
    label = "all policies" if tier is None else f"{tier.title()} fare only"
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(
            session_id=f"activity-1-{RUN_ID}",
            tags=["activity-1", variant],
            trace_name=trace_name,
        ):
            doc = retrieve("checked bag allowance", tier)[0]
            with langfuse.start_as_current_observation(
                name="activity-1-retrieval",
                as_type="retriever",
                input={"query": "checked bag allowance",
                       "filter": None if tier is None else {"tier": tier}},
                output={"doc_id": doc["id"], "tier": doc["tier"], "text": doc["text"]},
            ):
                pass
            messages = [
                {"role": "system", "content": "Answer using the retrieved policy document."},
                {"role": "user", "content": f"{customer_message}\n\nRetrieved policy:\n{doc['text']}"},
            ]
            started = time.time()
            response = client.chat.completions.create(
                model=MODEL, messages=messages, temperature=0, max_tokens=300,
                name="activity-1-generation",
            )
            latency = time.time() - started
            answer = response.choices[0].message.content
            trace_id = langfuse.get_current_trace_id()
            root.update(output={"answer": answer, "doc_id": doc["id"]})
    usage = response.usage
    return {
        "variant": variant,
        "label": label,
        "answer": answer,
        "doc": doc,
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "latency": latency,
        "trace_id": trace_id,
        "trace_url": record_trace(f"activity-1-{variant}", trace_id),
    }


def run_format(variant):
    trace_name = f"activity-2-output-{variant}"
    label = "free text" if variant == "unconstrained" else "structured"
    system = (
        "Summarize the customer's booking request in one sentence."
        if variant == "unconstrained"
        else "Return ONLY a JSON object with exactly these keys: origin, destination, travel_date, passengers, cabin. travel_date must be YYYY-MM-DD; passengers must be an integer; cabin must be economy or premium. No prose and no markdown fences."
    )
    request = "Book 2 passengers from Lisbon to Madrid on 2026-12-01, economy."
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(
            session_id=f"activity-2-{RUN_ID}",
            tags=["activity-2", variant],
            trace_name=trace_name,
        ):
            messages = [{"role": "system", "content": system}, {"role": "user", "content": request}]
            started = time.time()
            response = client.chat.completions.create(
                model=MODEL, messages=messages, temperature=0, max_tokens=300,
                name="activity-2-generation",
            )
            latency = time.time() - started
            answer = response.choices[0].message.content
            valid, parsed, reason = validate_booking_request(answer)
            trace_id = langfuse.get_current_trace_id()
            root.update(output={"valid": valid, "reason": reason, "parsed": parsed})
    usage = response.usage
    return {
        "variant": variant,
        "label": label,
        "answer": answer,
        "valid": valid,
        "parsed": parsed,
        "reason": reason,
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "latency": latency,
        "trace_id": trace_id,
        "trace_url": record_trace(f"activity-2-{variant}", trace_id),
    }


def run_hallucination(system_prompt, variant):
    trace_name = f"activity-3-hallucination-{variant}"
    label = "before fix" if variant == "broken" else "after fix"
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(
            session_id=f"activity-3-{RUN_ID}",
            tags=["activity-3", variant],
            trace_name=trace_name,
        ):
            doc = retrieve("checked bag allowance", "gold")[0]
            with langfuse.start_as_current_observation(
                name="activity-3-retrieval",
                as_type="retriever",
                input={"query": "checked bag allowance", "filter": {"tier": "gold"}},
                output={"doc_id": doc["id"], "tier": doc["tier"], "text": doc["text"]},
            ):
                pass
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"I'm a Gold member. How many checked bags are included in my Gold fare?\n\nRetrieved policy:\n{doc['text']}"},
            ]
            started = time.time()
            response = client.chat.completions.create(
                model=MODEL, messages=messages, temperature=0, max_tokens=800,
                name="activity-3-generation",
            )
            latency = time.time() - started
            answer = response.choices[0].message.content
            trace_id = langfuse.get_current_trace_id()
            root.update(output={"answer": answer, "doc_id": doc["id"]})
    usage = response.usage
    return {
        "variant": variant,
        "label": label,
        "answer": answer,
        "doc": doc,
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "latency": latency,
        "trace_id": trace_id,
        "trace_url": record_trace(f"activity-3-{variant}", trace_id),
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
        doc = run["doc"]
        print(f"\n{run['label']}")
        print(f"  retrieved: {doc['id']} ({doc['tier']} fare) — {doc['title']}")
        print(f"  query terms matched: {doc['score']}")
        print(f"  answer: {run['answer']}")
        print(f"  tokens: {run['input_tokens']} in / {run['output_tokens']} out · latency: {run['latency']:.1f}s")
        print(f"  activity log: {run['trace_url']}")


def show_format_results(runs):
    for run in runs:
        print(f"\n{run['label']}")
        print(f"  answer: {run['answer']}")
        print(f"  validation: {'PASS' if run['valid'] else 'FAIL'} — {run['reason']}")
        parsed = run["parsed"]
        if isinstance(parsed, dict):
            fields = ", ".join(
                f"{key}={parsed.get(key)!r}"
                for key in ("origin", "destination", "travel_date", "passengers", "cabin")
            )
            print(f"  parsed fields: {fields}")
        print(f"  tokens: {run['input_tokens']} in / {run['output_tokens']} out · latency: {run['latency']:.1f}s")
        print(f"  activity log: {run['trace_url']}")


def show_hallucination_broken(run):
    print(f"\n{run['label']}")
    print(f"  answer: {run['answer']}")
    print(f"  retrieved policy: {run['doc']['text']}")
    print(f"  activity log: {run['trace_url']}")


def show_hallucination_fixed(broken, fixed):
    print(f"\nretrieved policy: {broken['doc']['text']}")
    for run in (broken, fixed):
        print(f"\n{run['label']}")
        print(f"  answer: {run['answer']}")
        print(f"  activity log: {run['trace_url']}")


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
        print(f"{run['label']}: {run['trace_url']}")
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
