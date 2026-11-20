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

LOST_AND_FOUND = CORPUS["activity_1"]["lost_and_found"]
REQUESTS = CORPUS["activity_2"]["requests"]
NOTICES = CORPUS["activity_3"]["notices"]
INSTRUCTIONS = CORPUS["activity_3"]["instructions"]
BOOKINGS = CORPUS["activity_4"]["bookings"]
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


LAST_RUN = {}  # trace name → trace id of this kernel's latest run, so checks wait for it


def announce(line, trace_id, trace_name):
    """The only thing a run prints: a status line and the activity-log link."""
    LAST_RUN[trace_name] = trace_id
    print(f"{line}  📎 Open the activity log: {trace_url(trace_id)}")
    langfuse.flush()


def _safe_run(run):
    """A run cell never shows a traceback: a model or network failure becomes one line."""
    def wrapper(*args, **kwargs):
        try:
            return run(*args, **kwargs)
        except Exception as exc:
            langfuse.flush()
            print(f"⚙️ Skye could not finish this run ({type(exc).__name__}). "
                  "Run the cell again; if it keeps happening, wave at the game master.")
    wrapper.__name__, wrapper.__doc__ = run.__name__, run.__doc__
    return wrapper


# ── Checks read Langfuse back through its API ─────────────────────────────────


class _NoTrace(Exception):
    """The mission's run has not reached Langfuse (yet)."""


def _roots(trace_name, limit=50):
    roots = langfuse.api.observations.get_many(
        name=trace_name, is_root_observation=True, limit=limit, fields="core,basic"
    ).data
    if not roots:
        raise _NoTrace(trace_name)
    return roots


def _trace_ids(trace_name, limit=50):
    return [root.trace_id for root in _roots(trace_name, limit)]


def _step_ids(trace_id, step_name):
    steps = langfuse.api.observations.get_many(trace_id=trace_id, name=step_name, fields="core").data
    return [step.id for step in steps]


def latest_facts(trace_name):
    """Facts of the newest run that recorded them (a crashed run records none and is skipped)."""
    roots = langfuse.api.observations.get_many(
        name=trace_name, is_root_observation=True, limit=5, fields="core,basic,metadata"
    ).data
    if not roots:
        raise _NoTrace(trace_name)
    if trace_name in LAST_RUN and LAST_RUN[trace_name] not in {root.trace_id for root in roots}:
        raise _NoTrace(trace_name)  # this kernel's latest run has not reached Langfuse yet
    for root in roots:
        metadata = root.metadata or {}
        facts = {key[len("facts."):]: value for key, value in metadata.items() if key.startswith("facts.")}
        if isinstance(metadata.get("facts"), dict):
            facts.update(metadata["facts"])
        if facts:
            return facts
    return {}


def has_comment(trace_name, step_name):
    """True when any trace with this name has a comment on the named step.

    step_name None means a comment on the whole trace. The Langfuse UI files that as a comment on
    the trace's top node (the root observation); the API can also file it on the trace itself.
    """
    return any(_commented(root.trace_id, root.id, step_name) for root in _roots(trace_name))


def _commented(trace_id, root_id, step_name):
    """True when this one trace has a comment on the named step (None: on the whole trace)."""
    if step_name is None:
        targets = [("TRACE", trace_id), ("OBSERVATION", root_id)]
    else:
        targets = [("OBSERVATION", step_id) for step_id in _step_ids(trace_id, step_name)]
    return any(langfuse.api.comments.get(object_type=object_type, object_id=object_id).data
               for object_type, object_id in targets)


def has_score(trace_name, step_name, score_name, value):
    for trace_id in _trace_ids(trace_name):
        for step_id in _step_ids(trace_id, step_name):
            scores = langfuse.api.scores.get_many(trace_id=trace_id, observation_id=step_id, name=score_name).data
            if any(float(score.value) == value for score in scores):
                return True
    return False


def stale_label_nudge(prompt_name, facts):
    """Nudge when a newer prompt version exists than the one Skye just ran."""
    if "prompt_version" not in facts:
        return None
    versions = langfuse.api.prompts.list(name=prompt_name).data[0].versions
    if max(versions) > facts["prompt_version"]:
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
    """Run every check of one activity (or all of them) and print the tally.

    Pick the winner missions are bonus: they get their own line and never block the ending.
    """
    chosen = [m for m, spec in MISSIONS.items() if activity is None or spec["activity"] == activity]
    core = [m for m in chosen if not MISSIONS[m].get("bonus")]
    duels = [m for m in chosen if MISSIONS[m].get("bonus")]
    done = sum(check(mission) for mission in core)
    print(f"\n🏁 {done} of {len(core)} missions done.")
    if duels:
        print("\n🥊 Pick the winner (bonus)")
        won = sum(check(mission) for mission in duels)
        print(f"\n🥊 {won} of {len(duels)} duels won.")
    if activity is None and core and done == len(core):
        print(SKYE_IS_BACK)


# ── Pick the winner: two runs in one session, comment on the one you would ship ─
# Each activity adds rows to DUELS and its runner to DUEL_RUNNERS. Row keys: activity, title,
# winner ("a" or "b"), status (the printed line), options {"a": kwargs, "b": kwargs} for the
# runner, prompts {"a": text, "b": text} or None (seeded as prompt duel-<mission>), hint, solved.

DUELS = {}
DUEL_RUNNERS = {}  # activity → runner(mission, option, overrides, session_id) -> trace id
DUEL_STEPS = {}    # activity → step names inside a duel trace (a comment there is not a pick)


def duel_trace_name(mission, option):
    return f"activity-{DUELS[mission]['activity']}-duel-{mission}-option-{option}"


def session_url(trace_id, session_id):
    return trace_url(trace_id).split("/traces/")[0] + f"/sessions/{session_id}"


@_safe_run
def run_duel(mission):
    """Run both options of a Pick the winner mission in one fresh session."""
    if mission not in DUELS:
        print(f"❓ No duel '{mission}'. Duels: {', '.join(DUELS)}")
        return
    row = DUELS[mission]
    session_id = f"activity-{row['activity']}-duel-{mission}-{RUN_ID}-{uuid.uuid4().hex[:4]}"
    trace_ids = {}
    for option in ("a", "b"):
        trace_ids[option] = DUEL_RUNNERS[row["activity"]](mission, option, row["options"][option], session_id)
        LAST_RUN[duel_trace_name(mission, option)] = trace_ids[option]
    print(f"{row['status']}  📎 Open the session: {session_url(trace_ids['a'], session_id)}")
    langfuse.flush()


def _duel_outcome(sessions):
    """sessions: [{"winner", "loser", "step"}] (comment flags) → won | loser | both | step | none."""
    if any(s["winner"] and not s["loser"] for s in sessions):
        return "won"
    if any(s["loser"] and not s["winner"] for s in sessions):
        return "loser"
    if any(s["winner"] and s["loser"] for s in sessions):
        return "both"
    if any(s["step"] for s in sessions):
        return "step"
    return "none"


def _duel_roots(mission, option):
    name = duel_trace_name(mission, option)
    roots = langfuse.api.observations.get_many(
        name=name, is_root_observation=True, limit=50, fields="core,basic").data
    if name in LAST_RUN and LAST_RUN[name] not in {root.trace_id for root in roots}:
        raise _NoTrace(name)  # this kernel's latest run has not reached Langfuse yet
    return roots


def _check_duel(mission):
    row = DUELS[mission]
    loser = "b" if row["winner"] == "a" else "a"
    roots = {"winner": _duel_roots(mission, row["winner"]), "loser": _duel_roots(mission, loser)}
    if not roots["winner"] and not roots["loser"]:
        raise _NoTrace(mission)
    sessions = {}
    for side, side_roots in roots.items():
        for root in side_roots:
            flags = sessions.setdefault(root.session_id, {"winner": False, "loser": False, "step": False})
            flags[side] = flags[side] or _commented(root.trace_id, root.id, None)
            flags["step"] = flags["step"] or any(
                _commented(root.trace_id, root.id, step) for step in DUEL_STEPS[row["activity"]])
    outcome = _duel_outcome(list(sessions.values()))
    return outcome == "won", {
        "won": "",
        "loser": row["hint"],
        "both": "Skye can only ship one. Pick one run and comment only on it.",
        "step": "That comment is on a step. Click the top line of the run you would ship.",
        "none": "Open the session, compare the two runs, and comment on the top line of the one you would ship.",
    }[outcome]


def _register_duels(activity):
    for mission, row in DUELS.items():
        if row["activity"] == activity:
            MISSIONS[mission] = {"activity": activity, "title": row["title"], "bonus": True,
                                 "check": lambda mission=mission: _check_duel(mission), "solved": row["solved"]}


def seed_duel_prompts():
    """Create prompt duel-<mission> (version 1 = option-a, version 2 = option-b) when missing."""
    for mission, row in DUELS.items():
        name = f"duel-{mission}"
        if row.get("prompts") and not langfuse.api.prompts.list(name=name).data:
            for option in ("a", "b"):
                langfuse.create_prompt(name=name, prompt=row["prompts"][option], labels=[f"option-{option}"])


seed_prompts()


LOG_QUERY = "bag found on board"
CUSTOMER_MESSAGE = (
    "HOLY MOLY! Gus here, flight SK101. Did anyone find my bag of fish? Big Bertha is in there, "
    "my best catch ever! And my lucky fishing hat?! I was wearing it when I caught Big Bertha."
)
GUS_FLIGHT = "SK101"
RAG_CONFIG = {"flight_filter": bool, "top_k": int}


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
    entries = LOST_AND_FOUND
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


LAST_ANSWER_USAGE = {"reasoning": 0, "answer": 0}  # tokens of the latest Activity 1 answer


def _remember_usage(response):
    usage = getattr(response, "usage", None)
    if usage is None or usage.completion_tokens is None:  # some endpoints send no usage
        LAST_ANSWER_USAGE.update(reasoning=0, answer=0)
        return
    details = getattr(usage, "completion_tokens_details", None)
    reasoning = (getattr(details, "reasoning_tokens", None) or 0) if details else 0
    LAST_ANSWER_USAGE.update(reasoning=reasoning, answer=max(usage.completion_tokens - reasoning, 0))


def _rag_trace(trace_name, prompt, items, search_input, session_id, *, message=CUSTOMER_MESSAGE,
               system=None, max_tokens=800, slow_seconds=0, search=True, extra_facts=None):
    """One traced Skye run: the search step, then the answer step linked to the prompt.

    search=False skips the search step; slow_seconds adds a slow double-check step;
    system replaces the prompt's text (prompt may then be None: no prompt link).
    """
    with langfuse.start_as_current_observation(name=trace_name, as_type="span") as root:
        with propagate_attributes(session_id=session_id, tags=["activity-1"], trace_name=trace_name):
            user = f"## Customer message\n{message}"
            if search:
                with langfuse.start_as_current_observation(
                    name="activity-1-retrieval",
                    as_type="retriever",
                    input=search_input,
                    output={"count": len(items),
                            "items": [{key: item[key] for key in ("id", "flight", "item", "text")}
                                      for item in items]},
                ):
                    pass
                entries = "\n".join(f"- {item['text']}" for item in items)
                user += f"\n\n## Lost-and-found entries (search results)\n{entries}"
            if slow_seconds:
                with langfuse.start_as_current_observation(
                    name="double-check-with-desk", as_type="span", input={"question": "is the desk still open?"}
                ) as step:
                    time.sleep(slow_seconds)
                    step.update(output={"desk": "still checking..."})
            response = client.chat.completions.create(
                model=MODEL, temperature=0, max_tokens=max_tokens, name="activity-1-generation",
                langfuse_prompt=prompt,
                messages=[
                    {"role": "system", "content": system if system is not None else prompt.prompt},
                    {"role": "user", "content": user},
                ],
            )
            _remember_usage(response)
            trace_id = langfuse.get_current_trace_id()
            record_facts(root, {"flight_filter": bool(search and search_input["filter"] is not None),
                                "top_k": search_input["top_k"] if search else 0,
                                "item_ids": [item["id"] for item in items] if search else [],
                                "search": bool(search), "max_tokens": max_tokens,
                                "slow_seconds": slow_seconds, **(extra_facts or {})}, prompt)
    return trace_id


@_safe_run
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
    announce("🛫 Skye answered Gus.", trace_id, "activity-1-rag")


def _check_1_1():
    return has_comment("activity-1-rag", None), (
        "Click the top line of the tree (activity-1-rag) and leave any comment there. Anything goes!")


def _check_1_2():
    if not has_comment("activity-1-rag", "activity-1-retrieval"):
        if has_comment("activity-1-rag", "activity-1-generation"):
            return False, ("Your comment is on the answer step. Skye only talked about what it was given. "
                           "The dolphin got in one step earlier. Which step was it?")
        return False, "Leave a comment on the step that brought the dolphin in."
    facts = latest_facts("activity-1-rag")
    ids = facts.get("item_ids") or []
    fixed = facts.get("flight_filter") is True and "lf-fish-bag-sk101" in ids and "lf-dolphin-sk205" not in ids
    if fixed:
        return True, ""
    return False, (stale_label_nudge("skye-lost-and-found", facts)
                   or "Comment found 👍 Now keep the dolphin out: in the Config of prompt "
                      "skye-lost-and-found, make the search look at Gus's flight only. Then rerun.")


def _check_1_3():
    facts = latest_facts("activity-1-rag")
    ids = facts.get("item_ids") or []
    if facts.get("flight_filter") is True and {"lf-fish-bag-sk101", "lf-fishing-hat-sk101"} <= set(ids):
        return True, ""
    return False, (stale_label_nudge("skye-lost-and-found", facts)
                   or "Skye still has no idea about the hat. Open the search step: how many things came "
                      "back, and how many did Gus lose?")


MISSIONS.update({
    "1.1": {"activity": 1, "title": "Say hi to the trace", "check": _check_1_1,
            "solved": "Hello, trace! You just left your first note in Langfuse."},
    "1.2": {"activity": 1, "title": "Who invited the dolphin?", "check": _check_1_2,
            "solved": "Finnegan is back on flight SK205. He splashed the pilot on the way."},
    "1.3": {"activity": 1, "title": "The hat nobody saw", "check": _check_1_3,
            "solved": "Big Bertha and the lucky hat are back together. Gus is crying happy tears into the hat."},
})


GUS_DUEL_SYSTEM = (
    "You are Skye, Skyline Travel's assistant. Answer Gus kindly and briefly. About his lost "
    "things, say only what the lost-and-found entries say. Airport facts you may use: the "
    "lost-and-found desk is at Gate 12, next to the giant pretzel. The way from Gate 3: walk past "
    "the coffee shop, take the escalator down, turn left at the giant pretzel, and the desk is on "
    "the right."
)
DUEL_STEPS[1] = ("activity-1-retrieval", "activity-1-generation", "double-check-with-desk")


def _gus_duel(mission, option, overrides, session_id):
    """One option of an Activity 1 duel: Gus's flight-only search unless the option says otherwise."""
    row, settings = DUELS[mission], {"max_tokens": 1500, **overrides}  # room for a thinking model
    prompt, system = None, GUS_DUEL_SYSTEM
    if row.get("prompts"):
        prompt = langfuse.get_prompt(f"duel-{mission}", label=f"option-{option}", cache_ttl_seconds=0)
        system = None
    if settings.get("max_tokens") == "cut":
        # Just enough tokens for the thinking and a third of the answer the other option gave.
        settings["max_tokens"] = LAST_ANSWER_USAGE["reasoning"] + max(LAST_ANSWER_USAGE["answer"] // 3, 5)
    search = settings.pop("search", True)
    if search == "whole_log":
        items, search_input, search = LOST_AND_FOUND, {"query": None, "filter": None, "top_k": len(LOST_AND_FOUND)}, True
    elif search:
        query, top_k = settings.pop("query", LOG_QUERY), settings.pop("top_k", 3)
        items = search_log(query, GUS_FLIGHT, top_k=top_k)
        search_input = {"query": query, "filter": {"flight": GUS_FLIGHT}, "top_k": top_k}
    else:
        items, search_input = [], {"query": None, "filter": None, "top_k": 0}
    return _rag_trace(duel_trace_name(mission, option), prompt, items, search_input, session_id,
                      message=row.get("message", CUSTOMER_MESSAGE), system=system, search=search,
                      extra_facts={"mission": mission, "option": option, "session_id": session_id}, **settings)


DUEL_RUNNERS[1] = _gus_duel
DUELS.update({
    "1.4": {"activity": 1, "title": "Pick the winner: the whole log", "winner": "a",
            "status": "🥊 Two Skyes looked for Big Bertha. Only one keeps the job.",
            "options": {"a": {}, "b": {"search": "whole_log"}}, "prompts": None,
            "hint": "Show the Tokens and Cost columns in Tracing → Traces. Both runs found Big Bertha. "
                    "Which one cost more?",
            "solved": "Same answer, way fewer tokens. Gus's wallet says thank you."},
    "1.5": {"activity": 1, "title": "The desk closes in 10 minutes", "winner": "b",
            "status": "🥊 Two Skyes told Gus where the desk is. Only one keeps the job.",
            "message": "HOLY MOLY! The lost-and-found desk closes in 10 minutes! Where is it? "
                       "I'm running! Well... walking very fast. Like a fish on a bicycle.",
            "options": {"a": {"slow_seconds": 6, "search": False}, "b": {"search": False}}, "prompts": None,
            "hint": "Open the Timeline of both runs. Gus has 10 minutes. Which Skye made him wait?",
            "solved": "Gus made it with 3 minutes to spare. He did a little victory dance."},
    "1.6": {"activity": 1, "title": "Directions to the desk", "winner": "a",
            "status": "🥊 Two Skyes gave Gus directions. Only one keeps the job.",
            "message": "I'm at Gate 3. How do I get to the lost-and-found desk? Step by step, please, "
                       "and tell me what I will see at every step. I once got lost on my own boat.",
            "options": {"a": {"search": False}, "b": {"search": False, "max_tokens": "cut"}}, "prompts": None,
            "hint": "Read the end of both answers. Did one of them stop in the middle?",
            "solved": "Gus followed every step and only walked into one door."},
    "1.7": {"activity": 1, "title": "Is Big Bertha still fresh?", "winner": "b",
            "status": "🥊 Two Skyes checked on Big Bertha. Only one keeps the job.",
            "message": "Is Big Bertha still fresh?? She has been in that bag since 6 in the morning! "
                       "Please tell me the truth. I can take it. Maybe.",
            "options": {"a": {"search": False}, "b": {"query": "fish ice fresh warm", "top_k": 2}},
            "prompts": {
                "a": "You are Skye, Skyline Travel's assistant. Never say you don't know. Always sound "
                     "100% sure, even when you have no facts. Customers love a confident answer.",
                "b": "You are Skye, Skyline Travel's assistant. Answer only with what the lost-and-found "
                     "entries say. If they don't say it, tell the customer you don't know.",
            },
            "hint": "Does each run have a search step? Where did each answer get its facts?",
            "solved": "Bad news, told kindly: Big Bertha is warm. Gus is already planning her a nice dinner."},
    "1.8": {"activity": 1, "title": "HOLY MOLY, in Norwegian", "winner": "a",
            "status": "🥊 Two Skyes answered Gus. Only one keeps the job.",
            "message": "HOLY MOLY! Hei Skye! Har dere funnet fiskeposen min? Big Bertha er der inne! "
                       "Og fiskehatten min?",
            "options": {"a": {}, "b": {}},
            "prompts": {
                "a": GUS_DUEL_SYSTEM + " Answer in the customer's language.",
                "b": GUS_DUEL_SYSTEM + " Answer in English.",
            },
            "hint": "Click the prompt version on each answer step and read it. Which language did Gus write in?",
            "solved": "Gus understood every word. He says 'tusen takk', which means 'thanks a thousand'."},
})
_register_duels(1)


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


@_safe_run
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
    announce("📸 Skye sent Coco's booking to the booking system.", trace_id, "activity-2-format")


@_safe_run
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
    announce("📨 Skye sent Coco's three requests to the booking system.", trace_id, "activity-2-format-batch")


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
    notices = NOTICES
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


@_safe_run
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
    announce("🐓 Skye answered Barnaby about his rooster.", trace_id, "activity-3-animals")


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


PIANO_QUESTION = "Good afternoon dear, this is Edna Ivory, booking SKY-2087. Where exactly is my grand piano?"
PARTNER_CACHE = {ref: "verified" for ref in BOOKINGS}
PARTNER_WAIT_SECONDS = 1.5
PARTNER_ATTEMPTS = 3


def _tool_schema(param):
    return {
        "type": "function",
        "function": {
            "name": "get_booking",
            "description": "Look up a booking by reference",
            "parameters": {"type": "object", "properties": {param: {"type": "string"}}, "required": [param]},
        },
    }


def _lookup(strict, **kwargs):
    """The booking tool. It reads booking_id; the 'forgiving' version tidies the reference and never fails."""
    ref = kwargs["booking_id"]
    if strict:
        match = re.search(r"SKY\W*_?(\d+)", ref.upper())
        key = f"SKY-{match.group(1)}" if match else ref.strip().upper()
        return {"booking_ref": key, **BOOKINGS[key]}
    key = ref.upper().replace("-", "")
    booking = BOOKINGS.get(key)
    if booking is None:
        key, booking = next(iter(BOOKINGS.items()))
    return {"booking_ref": key, **booking}


def _piano_movers(ref, cache_key):
    """Double-check with the piano movers' system; on a cache miss wait and ask again, up to three times."""
    checks = 0
    for attempt in range(1, PARTNER_ATTEMPTS + 1):
        checks += 1
        with langfuse.start_as_current_observation(
            name="piano-mover-check", as_type="span", input={"booking_ref": ref, "attempt": attempt}
        ) as step:
            if cache_key(ref) in PARTNER_CACHE:
                step.update(output={"cache": "hit"})
                break
            time.sleep(PARTNER_WAIT_SECONDS)
            step.update(output={"cache": "miss", "piano_movers": "no answer yet, they are lifting something"})
    return checks


@_safe_run
def run_piano(cache_key):
    """Edna asks where her piano is; Skye calls the get_booking tool configured in prompt skye-piano."""
    loaded = load_prompt("skye-piano", {"tool_param": str, "strict_lookup": bool})
    if loaded is None:
        return
    prompt, config = loaded
    tools = [_tool_schema(config["tool_param"])]
    facts = {"tool_called": False, "tool_error": False, "returned_ref": None, "piano_mover_checks": 0}
    with langfuse.start_as_current_observation(name="activity-4-piano", as_type="span") as root:
        with propagate_attributes(session_id=f"activity-4-{RUN_ID}", tags=["activity-4"], trace_name="activity-4-piano"):
            messages = [{"role": "system", "content": prompt.prompt}, {"role": "user", "content": PIANO_QUESTION}]
            first = client.chat.completions.create(
                model=MODEL, messages=messages, tools=tools, tool_choice="required", temperature=0,
                max_tokens=800, name="activity-4-generation-1", langfuse_prompt=prompt,
            )
            message = first.choices[0].message
            messages.append(message.model_dump(exclude_none=True))
            for number, call in enumerate(message.tool_calls or []):
                if number > 0:  # some models repeat the call; one lookup per question
                    messages.append({"role": "tool", "tool_call_id": call.id,
                                     "content": json.dumps({"error": "one lookup per question"})})
                    continue
                facts["tool_called"] = True
                with langfuse.start_as_current_observation(
                    name="get_booking", as_type="tool", input=call.function.arguments
                ) as tool:
                    try:
                        args = json.loads(call.function.arguments)
                        tool.update(input=args)
                        result = _lookup(config["strict_lookup"], **args)
                        tool.update(output=result)
                        facts["returned_ref"] = result["booking_ref"]
                        facts["piano_mover_checks"] += _piano_movers(result["booking_ref"], cache_key)
                    except Exception as exc:
                        result = {"error": f"{type(exc).__name__}: {exc}"}
                        tool.update(level="ERROR", status_message=result["error"], output=result)
                        facts["tool_error"] = True
                messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
            client.chat.completions.create(
                model=MODEL, messages=messages, tools=tools, tool_choice="none", temperature=0,
                max_tokens=800, name="activity-4-generation-2", langfuse_prompt=prompt,
            )
            trace_id = langfuse.get_current_trace_id()
            record_facts(root, facts, prompt)
    announce("🎹 Skye answered Edna.", trace_id, "activity-4-piano")


def _check_4_1():
    commented = has_comment("activity-4-piano", "get_booking")
    facts = latest_facts("activity-4-piano")
    if commented and facts.get("tool_error") is False and facts.get("returned_ref"):
        return True, ""
    if facts.get("tool_called") is False:
        return False, "Skye answered without calling the tool this time. Run the mission cell again."
    if not commented:
        return False, "Find the step that failed (it is red in the tree) and leave a comment on it."
    return False, (stale_label_nudge("skye-piano", facts)
                   or "Comment found 👍 Read the tool step's Input and its error: what did Skye send, "
                      "and what did the tool expect? The config of skye-piano names the tool's parameter.")


def _check_4_2():
    scored = has_score("activity-4-piano", "get_booking", SCORE_NAME, 0)
    facts = latest_facts("activity-4-piano")
    if scored and facts.get("returned_ref") == "SKY-2087":
        return True, ""
    if not scored:
        return False, "Annotate the tool step that returned the wrong trip with the score 'correct' = false."
    return False, (stale_label_nudge("skye-piano", facts)
                   or "Score found 👍 The lookup still guesses. Look at the config of skye-piano.")


def _check_4_3():
    facts = latest_facts("activity-4-piano")
    if facts.get("returned_ref") == "SKY-2087" and facts.get("piano_mover_checks") == 1:
        return True, ""
    if facts.get("returned_ref") != "SKY-2087":
        return False, "Finish 4.2 first: Skye has to find Edna's booking before anyone can call the piano movers."
    return False, (f"The piano movers were asked {facts.get('piano_mover_checks')} times. Open the Timeline: "
                   "why does the cache never answer?")


MISSIONS.update({
    "4.1": {"activity": 4, "title": "The wrong label", "check": _check_4_1,
            "solved": "Skye and the tool finally speak the same language."},
    "4.2": {"activity": 4, "title": "The wrong trip", "check": _check_4_2,
            "solved": "The piano is a piano again. Gus's fish no longer weigh 400 kg."},
    "4.3": {"activity": 4, "title": "The slow lookup", "check": _check_4_3,
            "solved": "One call to the piano movers. They can put the piano down now."},
})


seed_duel_prompts()
