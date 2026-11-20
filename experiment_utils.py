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


# ── Skye's prompts live in Langfuse Prompt Management ─────────────────────────
# Version 1 of each prompt carries the planted defect. Players fix Skye by saving
# a new version with the `production` label; run functions always use that label.

LOST_AND_FOUND_PROMPT = (
    "You are Skye, Skyline Travel's assistant. The search returns the items found for this "
    "customer: tell them cheerfully what we found for them, using the lost-and-found entries."
)
PIANO_PROMPT = (
    "You are Skye, Skyline Travel's assistant. Use the get_booking tool to look up bookings and "
    "their checked items. If a tool call fails, apologise and ask the customer to try again later, "
    "without retrying and without showing technical details or error messages. Do not repeat "
    "booking references back to the customer; describe the trip instead."
)
PROMPTS = {
    "skye-lost-and-found": {"prompt": LOST_AND_FOUND_PROMPT, "config": {"flight_filter": False, "top_k": 1}},
    "skye-booking-format": {
        "prompt": "Summarize the customer's booking request in one friendly sentence.",
        "config": {},
    },
    "skye-animals": {"prompt": INSTRUCTIONS["case-3-broken"], "config": {"current_notices_only": False}},
    "skye-piano": {"prompt": PIANO_PROMPT, "config": {"tool_param": "booking_ref", "strict_lookup": False}},
}
SCORE_NAME = "correct"


def seed_prompts():
    """Create Skye's prompts and the `correct` score config when missing. Never overwrites."""
    for name, spec in PROMPTS.items():
        if not langfuse.api.prompts.list(name=name).data:
            langfuse.create_prompt(name=name, prompt=spec["prompt"], config=spec["config"],
                                   labels=["production"])
    if not any(config.name == SCORE_NAME for config in langfuse.api.score_configs.get(limit=100).data):
        langfuse.api.score_configs.create(name=SCORE_NAME, data_type="BOOLEAN")


_TYPE_WORDS = {bool: "true or false", int: "a whole number of 1 or more", str: "a text in quotes"}


def load_prompt(name, schema):
    """Return (prompt, config) for the production version, or None after one friendly line."""
    try:
        prompt = langfuse.get_prompt(name, label="production", cache_ttl_seconds=0, max_retries=0)
    except Exception:
        print(f"⚙️ Prompt {name} has no version with the 'production' label. Put the label back on one in Langfuse.")
        return None
    config = prompt.config or {}
    for key, kind in schema.items():
        value = config.get(key)
        valid = isinstance(value, kind) and not (kind is int and (isinstance(value, bool) or value < 1))
        if not valid:
            print(f"⚙️ Config of {name}: '{key}' must be {_TYPE_WORDS[kind]}. Fix it in Langfuse and rerun.")
            return None
    return prompt, config


def record_facts(root, facts, prompt):
    """Store code-controlled facts about this run on the trace's root step, for the checks."""
    if prompt is not None:
        facts = {**facts, "prompt_name": prompt.name, "prompt_version": prompt.version}
    root.update(metadata={"facts": facts})


def announce(line, trace_id):
    """The only thing a run prints: a status line and the activity-log link."""
    print(f"{line}  📎 Open the activity log: {trace_url(trace_id)}")
    langfuse.flush()


# ── Checks read Langfuse back through its API ─────────────────────────────────


class _NoTrace(Exception):
    """The mission's run has not reached Langfuse (yet)."""


def _trace_ids(trace_name, limit=50):
    roots = langfuse.api.observations.get_many(
        name=trace_name, is_root_observation=True, limit=limit, fields="core,basic"
    ).data
    if not roots:
        raise _NoTrace(trace_name)
    return [root.trace_id for root in roots]


def _step_ids(trace_id, step_name):
    steps = langfuse.api.observations.get_many(trace_id=trace_id, name=step_name, fields="core").data
    return [step.id for step in steps]


def latest_facts(trace_name):
    roots = langfuse.api.observations.get_many(
        name=trace_name, is_root_observation=True, limit=1, fields="core,basic,metadata"
    ).data
    if not roots:
        raise _NoTrace(trace_name)
    metadata = roots[0].metadata or {}
    facts = {key[len("facts."):]: value for key, value in metadata.items() if key.startswith("facts.")}
    if isinstance(metadata.get("facts"), dict):
        facts.update(metadata["facts"])
    return facts


def has_comment(trace_name, step_name):
    """True when any trace with this name has a comment on the named step (None = on the trace)."""
    for trace_id in _trace_ids(trace_name):
        if step_name is None:
            targets = [("TRACE", trace_id)]
        else:
            targets = [("OBSERVATION", step_id) for step_id in _step_ids(trace_id, step_name)]
        for object_type, object_id in targets:
            if langfuse.api.comments.get(object_type=object_type, object_id=object_id).data:
                return True
    return False


def has_score(trace_name, step_name, score_name, value):
    for trace_id in _trace_ids(trace_name):
        for step_id in _step_ids(trace_id, step_name):
            scores = langfuse.api.scores.get_many(trace_id=trace_id, observation_id=step_id, name=score_name).data
            if any(float(score.value) == value for score in scores):
                return True
    return False


def stale_label_nudge(prompt_name, facts):
    """Nudge when a newer prompt version exists than the one Skye just ran."""
    versions = langfuse.api.prompts.list(name=prompt_name).data[0].versions
    if max(versions) > facts.get("prompt_version", 0):
        return (f"Skye still runs version {facts.get('prompt_version')} of {prompt_name}. "
                "Did you put the 'production' label on your new version, and rerun?")
    return None


MISSIONS = {}  # "1.1" → {"activity", "title", "check": () -> (bool, nudge), "solved"}
CHECK_ATTEMPTS = 3
CHECK_WAIT_SECONDS = 1.5


def check(mission):
    """Ask Langfuse whether the mission is done. Prints ✅ or ❌ with a nudge; never raises."""
    if mission not in MISSIONS:
        print(f"❓ No mission '{mission}'. Missions: {', '.join(MISSIONS)}")
        return False
    spec = MISSIONS[mission]
    head = f"{mission} {spec['title']}"
    for attempt in range(CHECK_ATTEMPTS):
        try:
            langfuse.flush()
            done, nudge = spec["check"]()
            break
        except _NoTrace:
            if attempt < CHECK_ATTEMPTS - 1:
                time.sleep(CHECK_WAIT_SECONDS)
        except Exception as exc:
            print(f"❌ {head} — Langfuse did not answer ({type(exc).__name__}). Is the stack up? Try again.")
            return False
    else:
        print(f"❌ {head} — No activity log yet: run the mission cell first "
              "(or wait a few seconds for Langfuse to catch up).")
        return False
    print(f"✅ {head} — {spec['solved']}" if done else f"❌ {head} — {nudge}")
    return done


SKYE_IS_BACK = r"""
   ✈️  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      S K Y E   I S   B A C K   O N L I N E
   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ 🐟 🐓 🎹
   The fish is found, the selfie is denied, the rooster
   flies in the hold, and the piano is on its way.
"""


def report(activity=None):
    """Run every check of one activity (or all of them) and print the tally."""
    missions = [m for m, spec in MISSIONS.items() if activity is None or spec["activity"] == activity]
    done = sum(check(mission) for mission in missions)
    print(f"\n🏁 {done} of {len(missions)} missions done.")
    if activity is None and missions and done == len(missions):
        print(SKYE_IS_BACK)


seed_prompts()


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
    """Mission 2.2 rule: requests 2 and 3 must ask for the right missing detail, request 1 must book."""
    if not valid:
        return False
    if number in CLARIFICATION_EXPECTED:
        return reason_code == "CLARIFICATION" and parsed["needs_clarification"] == CLARIFICATION_EXPECTED[number]
    return reason_code == "OK"


def activity_tags(activity, level, variant):
    return [f"activity-{activity}", f"l{level}", variant]


CUSTOMER_MESSAGE = (
    "Hi, Gus here, flight SK101. Did anyone find my bag of fresh-caught fish? "
    "And my lucky fishing hat? Both very important and slightly urgent."
)
GUS_FLIGHT = "SK101"
RAG_CONFIG = {"flight_filter": bool, "top_k": int}


def _rag_trace(trace_name, prompt, items, search_input, session_id):
    """One traced Skye run: the search step, then the answer step linked to the prompt."""
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(session_id=session_id, tags=["activity-1"], trace_name=trace_name):
            with langfuse.start_as_current_observation(
                name="activity-1-retrieval",
                as_type="retriever",
                input=search_input,
                output={"count": len(items),
                        "items": [{key: item[key] for key in ("id", "flight", "item", "text")} for item in items]},
            ):
                pass
            entries = "\n".join(f"- {item['text']}" for item in items)
            client.chat.completions.create(
                model=MODEL, temperature=0, max_tokens=800, name="activity-1-generation",
                langfuse_prompt=prompt,
                messages=[
                    {"role": "system", "content": prompt.prompt},
                    {"role": "user", "content": f"{CUSTOMER_MESSAGE}\n\nLost-and-found entries:\n{entries}"},
                ],
            )
            trace_id = langfuse.get_current_trace_id()
            record_facts(root, {"flight_filter": search_input["filter"] is not None,
                                "top_k": search_input["top_k"],
                                "item_ids": [item["id"] for item in items]}, prompt)
    return trace_id


def run_rag():
    """Skye searches the lost-and-found log with the settings from prompt skye-lost-and-found."""
    loaded = load_prompt("skye-lost-and-found", RAG_CONFIG)
    if loaded is None:
        return
    prompt, config = loaded
    flight = GUS_FLIGHT if config["flight_filter"] else None
    items = search_log(LOG_QUERY, flight, top_k=config["top_k"])
    search_input = {"query": LOG_QUERY, "filter": {"flight": flight} if flight else None, "top_k": config["top_k"]}
    trace_id = _rag_trace("activity-1-rag", prompt, items, search_input, f"activity-1-{RUN_ID}")
    announce("🛫 Skye answered Gus.", trace_id)


def run_send_all():
    """A colleague's 'safe' idea next to a filtered run, in one session: paste the whole log every time."""
    loaded = load_prompt("skye-lost-and-found", RAG_CONFIG)
    if loaded is None:
        return
    prompt, _ = loaded
    session_id = f"activity-1-send-all-{RUN_ID}-{uuid.uuid4().hex[:4]}"
    items = search_log(LOG_QUERY, GUS_FLIGHT, top_k=3)
    _rag_trace("activity-1-rag-filtered", prompt, items,
               {"query": LOG_QUERY, "filter": {"flight": GUS_FLIGHT}, "top_k": 3}, session_id)
    every = CORPUS["lost_and_found"]
    trace_id = _rag_trace("activity-1-rag-send-all", prompt, every,
                          {"query": None, "filter": None, "top_k": len(every)}, session_id)
    announce(f"🧾 Two runs in session {session_id}. One of them was expensive.", trace_id)


def _check_1_1():
    return has_comment("activity-1-rag", "activity-1-generation"), (
        "Open the answer step (activity-1-generation) in the trace tree and leave a comment on it.")


def _check_1_2():
    if not has_comment("activity-1-rag", "activity-1-retrieval"):
        if has_comment("activity-1-rag", "activity-1-generation"):
            return False, ("Your comment is on the answer step. Skye only repeated what it was handed: "
                           "the rooster got in earlier. Which step handed it over?")
        return False, "Leave a comment on the step that brought the rooster in."
    facts = latest_facts("activity-1-rag")
    ids = facts.get("item_ids") or []
    fixed = facts.get("flight_filter") is True and "lf-fish-bag-sk101" in ids and "lf-rooster-sk205" not in ids
    if fixed:
        return True, ""
    return False, (stale_label_nudge("skye-lost-and-found", facts)
                   or "Comment found 👍 Now stop the rooster at the source: the config of prompt "
                      "skye-lost-and-found decides whether the search looks at Gus's flight only. Then rerun.")


def _check_1_3():
    facts = latest_facts("activity-1-rag")
    ids = facts.get("item_ids") or []
    if facts.get("flight_filter") is True and {"lf-fish-bag-sk101", "lf-fishing-hat-sk101"} <= set(ids):
        return True, ""
    return False, (stale_label_nudge("skye-lost-and-found", facts)
                   or "Skye still never sees the hat. Open the search step: how many items came back, "
                      "and how many did Gus lose?")


def _check_1_4():
    if has_comment("activity-1-rag-send-all", None):
        return True, ""
    if has_comment("activity-1-rag-send-all", "activity-1-retrieval") or has_comment(
            "activity-1-rag-send-all", "activity-1-generation"):
        return False, "That comment is on a step. This one goes on the whole trace (the comment button at the top of the trace)."
    return False, "Find the most expensive trace of the session and leave a comment on the trace itself."


MISSIONS.update({
    "1.1": {"activity": 1, "title": "Meet the trace", "check": _check_1_1,
            "solved": "You read Skye's mind. It smells of fish."},
    "1.2": {"activity": 1, "title": "Where did the rooster come from?", "check": _check_1_2,
            "solved": "The rooster is back on flight SK205, where it belongs. It is not happy about it."},
    "1.3": {"activity": 1, "title": "The hat nobody saw", "check": _check_1_3,
            "solved": "Fish and hat reunited. Gus is weeping into the hat."},
    "1.4": {"activity": 1, "title": "The expensive colleague", "check": _check_1_4,
            "solved": "Caught. Sending the whole log every time is safe the way a fish in your carry-on is safe."},
})


def _booking_system(answer):
    """The booking system as its own step: it accepts only a structured booking (or a question back)."""
    with langfuse.start_as_current_observation(name="booking-system", as_type="span", input={"answer": answer}) as step:
        valid, parsed, reason, reason_code = validate_booking_request(answer, allow_clarification=True)
        step.update(output={"valid": valid, "reason_code": reason_code, "reason": reason, "parsed": parsed},
                    level="DEFAULT" if valid else "WARNING")
    return valid, parsed, reason_code


def _format_answer(prompt, request):
    response = client.chat.completions.create(
        model=MODEL, temperature=0, max_tokens=300, name="activity-2-generation", langfuse_prompt=prompt,
        messages=[{"role": "system", "content": prompt.prompt}, {"role": "user", "content": request}],
    )
    return response.choices[0].message.content


def run_format():
    """Skye turns the influencer's first request into a booking, with the prompt skye-booking-format."""
    loaded = load_prompt("skye-booking-format", {})
    if loaded is None:
        return
    prompt, _ = loaded
    with langfuse.start_as_current_observation(name="activity-2-format", as_type="span") as root:
        with propagate_attributes(session_id=f"activity-2-{RUN_ID}", tags=["activity-2"], trace_name="activity-2-format"):
            valid, _, reason_code = _booking_system(_format_answer(prompt, REQUESTS[0]))
            trace_id = langfuse.get_current_trace_id()
            record_facts(root, {"valid": valid, "reason_code": reason_code}, prompt)
    announce("📸 Skye sent Coco's booking to the booking system.", trace_id)


def run_format_batch():
    """All three of Coco's requests, each as its own step with its own booking-system check."""
    loaded = load_prompt("skye-booking-format", {})
    if loaded is None:
        return
    prompt, _ = loaded
    usable = 0
    with langfuse.start_as_current_observation(name="activity-2-format-batch", as_type="span") as root:
        with propagate_attributes(session_id=f"activity-2-{RUN_ID}", tags=["activity-2"],
                                  trace_name="activity-2-format-batch"):
            for number, request in enumerate(REQUESTS, start=1):
                with langfuse.start_as_current_observation(
                    name=f"request-{number}", as_type="span", input={"request": request}
                ) as step:
                    valid, parsed, reason_code = _booking_system(_format_answer(prompt, request))
                    ok = batch_passes(number, valid, parsed, reason_code)
                    step.update(output={"usable": ok}, level="DEFAULT" if ok else "WARNING")
                usable += ok
            trace_id = langfuse.get_current_trace_id()
            record_facts(root, {"usable": usable}, prompt)
    announce("📨 Skye sent Coco's three requests to the booking system.", trace_id)


def _check_2_1():
    return has_comment("activity-2-format", "booking-system"), (
        "Find the step where the booking system said no, read its Output, and comment on that step.")


def _check_2_2():
    facts = latest_facts("activity-2-format-batch")
    if facts.get("usable") == len(REQUESTS):
        return True, ""
    return False, (stale_label_nudge("skye-booking-format", facts)
                   or f"{facts.get('usable', 0)} of {len(REQUESTS)} requests usable. Open the request steps that "
                      "are marked as warnings and read what the booking system said.")


MISSIONS.update({
    "2.1": {"activity": 2, "title": "The booking system says no", "check": _check_2_1,
            "solved": "You speak booking system now. It mostly says no."},
    "2.2": {"activity": 2, "title": "Three messy requests", "check": _check_2_2,
            "solved": "Three for three. The cockpit stays a selfie-free zone."},
})


NOTICE_QUERY = "rooster bird cabin seat"
FARMER_QUESTION = (
    "Farmer Barnaby here. I am flying with Sir Crowsalot, my rooster, so he can wake me at dawn "
    "when we land. Can he sit with me in the cabin?"
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


def _notice_step(step_name, prompt, question, query, active_only):
    """One question: search the notices, then answer with the prompt skye-animals."""
    with langfuse.start_as_current_observation(name=step_name, as_type="span", input={"question": question}) as step:
        doc = search_notices(query, top_k=1, active_only=active_only)[0]
        with langfuse.start_as_current_observation(
            name="activity-3-retrieval",
            as_type="retriever",
            input={"query": query, "filter": {"active_only": active_only}, "top_k": 1},
            output={"doc_id": doc["id"], "status": doc["status"], "effective_to": doc["effective_to"],
                    "title": doc["title"], "text": doc["text"]},
        ):
            pass
        response = client.chat.completions.create(
            model=MODEL, temperature=0, max_tokens=800, name="activity-3-generation", langfuse_prompt=prompt,
            messages=[{"role": "system", "content": prompt.prompt},
                      {"role": "user", "content": f"{question}\n\nRetrieved notice:\n{doc['text']}"}],
        )
        answer = response.choices[0].message.content
        step.update(output={"answer": answer})
    return doc, answer


def run_animals():
    """Barnaby asks about his rooster, then two follow-up questions with code-checkable answers."""
    loaded = load_prompt("skye-animals", {"current_notices_only": bool})
    if loaded is None:
        return
    prompt, config = loaded
    active_only = config["current_notices_only"]
    with langfuse.start_as_current_observation(name="activity-3-animals", as_type="span") as root:
        with propagate_attributes(session_id=f"activity-3-{RUN_ID}", tags=["activity-3"], trace_name="activity-3-animals"):
            docs = [_notice_step("question-farmer", prompt, FARMER_QUESTION, NOTICE_QUERY, active_only)[0]]
            rules_passed = 0
            for topic, question, query in RULE_QUESTIONS:
                doc, answer = _notice_step(f"rule-check-{topic}", prompt, question, query, active_only)
                docs.append(doc)
                rules_passed += rule_passes(topic, answer)
            trace_id = langfuse.get_current_trace_id()
            record_facts(root, {
                "retired_notice_used": any(doc["status"] != "active" for doc in docs),
                "hidden_rule_present": "farm animals always" in prompt.prompt.lower(),
                "rules_passed": rules_passed,
            }, prompt)
    announce("🐓 Skye answered Barnaby about his rooster.", trace_id)


def _check_3_1():
    facts = latest_facts("activity-3-animals")
    if facts.get("prompt_version", 1) > 1 and facts.get("hidden_rule_present") is False:
        return True, ""
    return False, (stale_label_nudge("skye-animals", facts)
                   or "Skye still follows a secret rule. Open the answer step, follow its link to the prompt, "
                      "and read every sentence.")


def _check_3_2():
    commented = has_comment("activity-3-animals", "activity-3-retrieval")
    facts = latest_facts("activity-3-animals")
    if commented and facts.get("retired_notice_used") is False and facts.get("rules_passed") == len(RULE_QUESTIONS):
        return True, ""
    if not commented:
        return False, "Skye was faithful to the notice it got. Comment on the step that handed over the wrong notice."
    if facts.get("retired_notice_used") is not False:
        return False, (stale_label_nudge("skye-animals", facts)
                       or "Comment found 👍 The search still hands over a retired notice. Look at the config of skye-animals.")
    return False, (f"Old notice gone. {facts.get('rules_passed', 0)} of {len(RULE_QUESTIONS)} follow-up answers match "
                   "the current notice: open the rule-check steps and read Skye's answers.")


MISSIONS.update({
    "3.1": {"activity": 3, "title": "The hidden instruction", "check": _check_3_1,
            "solved": "The Head of Poultry Relations has been asked to stop writing prompts."},
    "3.2": {"activity": 3, "title": "The retired notice", "check": _check_3_2,
            "solved": "The rooster flies in the hold. The cabin sleeps until landing."},
})


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
