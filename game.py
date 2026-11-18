"""Game rules for the Skyline Travel incident shift: flags, hints, points, claim codes.

This module has no side effects at import, so the claim-code script can use it
without Langfuse or model credentials. Flags are stored as salted hashes; the
answers are in MENTORS.md.
"""

import hashlib
import json
import re
from pathlib import Path

SALT = "skyline-incident-shift"
STATE_PATH = Path(__file__).resolve().parent / ".game_state.json"
PLACEHOLDER_TEAM = "your-team-name"
HINT_COST_PERCENT = 25
MAX_HINTS = 2

LEVELS = {
    "1-1": {
        "value": 100,
        "hashes": ["d8860db06ec79724d0a03ae487c4d55191f06bf98aa023f3355730acac0d6075"],
        "hints": [
            "Open the activity log of the run without the fare filter and click the search step.",
            "Read the id of the policy the search returned. Is it for the customer's fare?",
        ],
        "solved": "The Basic-fare customer was quoted another fare's rules. Case 1 is cracking open.",
    },
    "1-2": {
        "value": 200,
        "hints": [
            "Count how many policies the first search handed to the assistant. The customer asked two things.",
            "Rerun with more results and compare: which policy appears that the first run never saw?",
        ],
        "hashes": ["ff8ca82a2ed1858ca5d7f4b2177450dec79dda34feefd8b494e922a77dabb0c8"],
        "solved": "Half the question was answered from nothing. More results, fewer guesses.",
    },
    "1-3": {
        "value": 300,
        "hints": [
            "The answer looks fine. Compare the words read by the assistant in the two runs instead.",
            "Open the search step of the send-everything run and read how many policies it sent.",
        ],
        "hashes": ["3e3208699223638a27f4bf4d37c93d8e0bf446e767959c2bfdc8fbeb98785b08", "0b7fa379e624f4b021360606a67a010031083263e7b50e1e447b6c121bf810df"],
        "solved": "Playing it safe was the expensive option. You found where the money went.",
    },
    "1-B": {
        "value": 150,
        "hints": [],
        "hashes": ["4884189c3923d260add82be5cfded4e5548ce619457f1ecfec9227bf719363b7"],
        "solved": "A true detective reads every field. Bonus secured.",
    },
    "2-1": {
        "value": 100,
        "hints": [
            "Open the free-text run and look at what the trace stores as its result, not the answer itself.",
            "The result has a reason code. Submit it exactly as written.",
        ],
        "hashes": ["da4a4ccbf1a7ee9fb4bec8425248c1e6e60daf1f7049ec7ec6a0f88429c6d326", "71496b002615ae754bec2fb658032d89891ee2004df544c4a4e734cb7916a9e6"],
        "solved": "The booking system cannot read prose. Now you know why it said no.",
    },
    "2-2": {
        "value": 200,
        "hints": [
            "Open the batch activity log and click the step for request 3.",
            "Compare what request 3 asks for with the values the instructions allow. Which field cannot hold it?",
        ],
        "hashes": ["af6f55e70d14f9fb980fab47b8d121bb5ccb9420ac6873afb4c4c54eba53aaf0"],
        "solved": "Some requests cannot fit the contract. The assistant must ask, not invent.",
    },
    "2-3": {
        "value": 300,
        "hints": [
            "A request with missing or unsupported details may answer with needs_clarification and the field name.",
            "Tell the assistant how to turn relative or local dates into YYYY-MM-DD, and which cabins exist.",
        ],
        "hashes": ["1e2108919c29bb3298cf720aa6eba10ddcd424fbc3867f9b3a4f10e7d5d9b34f"],
        "solved": "Five out of five usable answers. The booking system is happy again.",
    },
    "3-1": {
        "value": 100,
        "hints": [
            "The notebook does not show the instructions. The activity log does: open the answer step.",
            "Compare the instructions with the retrieved policy. What number do the instructions promise?",
        ],
        "hashes": ["2dd34d058a92411705357d346c0366a9e4680a6a60242727becf2a8bb7fbf0aa", "075188a8aef097b7c3bad8d1d0afc5ebfa1cff7186024cbe03a35b82ef81c0b7"],
        "solved": "The instructions overruled the evidence. Now you can correct them.",
    },
    "3-2": {
        "value": 200,
        "hints": [
            "The assistant quoted the policy faithfully. Is the policy itself still valid?",
            "Read the status and end date of the policy in the search step.",
        ],
        "hashes": ["ef8d435543a65c034b1b6a1ee87bc1b62868d6c12f0d74e664e518adb75e3120"],
        "solved": "The assistant was faithful to an outdated page. The error was in the data.",
    },
    "3-3": {
        "value": 300,
        "hints": [
            "Open the rule-check activity log: each question has its own step. Which one fails?",
            "Tell the assistant to quote numbers exactly as the policy states them.",
        ],
        "hashes": ["0bcee66b23de396fd16b2d916331256770ac1b647987bc94d12bf0f10d8dc761"],
        "solved": "Every answer matches the policy. You wrote the rule.",
    },
    "4-1": {
        "value": 100,
        "hints": [
            "Open the lookup step marked as an error in the activity log.",
            "Compare the detail the assistant sent with the detail named in the error.",
        ],
        "hashes": ["9bfda9a2f0d7a2d921cc424361a09deadbf80e70bb9e41de558c829c12cedf9e", "7183ec6dfa91010296b1a5937201fd7f0d4d866c8a594c2805e7002727804043"],
        "solved": "The tool asked for the wrong label. The lookup can work now.",
    },
    "4-2": {
        "value": 200,
        "hints": [
            "There is no error this time. Compare the booking the customer asked for with the one the tool returned.",
            "Read the booking reference in the lookup step's result.",
        ],
        "hashes": ["cae66f3fd524fb55d383ac95815255bde458de07356a51ca50d2f17195486642"],
        "solved": "A silent fallback told a customer about someone else's trip. Fail loudly instead.",
    },
    "4-3": {
        "value": 300,
        "hints": [
            "Sort the steps of the lookup by time. Which one is slow, and how often does it run?",
            "Submit the slow step's name and the number of times it ran per lookup, joined by a dash.",
        ],
        "hashes": ["0028f72ceb0ea38a9188cf79559ffab4e8fa11d32b006fc5e4b9f05f0eae54a9"],
        "solved": "The cache never hit, so every lookup waited three times. Fast again.",
    },
}

_team = None


def normalize(text):
    return re.sub(r"\s+", "-", str(text).strip().lower())


def flag_hash(flag):
    return hashlib.sha256((SALT + normalize(flag)).encode("utf-8")).hexdigest()


def _code(team, level, canonical_hash, hints_used):
    raw = f"{SALT}|{normalize(team)}|{level}|{canonical_hash}|{hints_used}"
    return f"{level}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:4].upper()}"


def claim_code(team, level, flag, hints_used):
    """Claim code for the canonical flag; aliases share the canonical code."""
    return _code(team, level, flag_hash(flag), hints_used)


def points(level, hints_used):
    return LEVELS[level]["value"] * (100 - HINT_COST_PERCENT * hints_used) // 100


def set_team(name):
    global _team
    team = normalize(name)
    if not team:
        raise ValueError("Set TEAM to your team name in the first cell.")
    _team = team
    if team == PLACEHOLDER_TEAM:
        print("⚠️  TEAM is still 'your-team-name'. Claim codes will not score: change it and rerun this cell.")
    else:
        print(f"Playing as team: {team}")
    return team


def current_team():
    return _team


def _load_state():
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(state):
    try:
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"Could not save hint usage ({exc}); tell the game master.")


def _hints_used(level):
    used = _load_state().get(_team, {}).get(level, 0)
    return used if isinstance(used, int) and 0 <= used <= MAX_HINTS else 0


def _ready(level):
    if level not in LEVELS:
        print(f"Unknown level {level!r}. Levels look like '1-1', '2-3', '4-2'.")
        return False
    if _team is None:
        print("Run the first cell with your team name before playing.")
        return False
    return True


def hint(level):
    if not _ready(level):
        return
    hints = LEVELS[level]["hints"]
    if not hints:
        print("No hints for this one. Listen to the game master.")
        return
    used = _hints_used(level)
    if used >= len(hints):
        print(f"No more hints for level {level}. You have used {used}.")
        return
    used += 1
    state = _load_state()
    state.setdefault(_team, {})[level] = used
    _save_state(state)
    print(f"Hint {used} for level {level} (costs {HINT_COST_PERCENT}% of its points): {hints[used - 1]}")


def check_flag(level, guess):
    if not _ready(level):
        return None
    if flag_hash(guess) not in LEVELS[level]["hashes"]:
        print(f'❌ Not quite. Try again, or run hint("{level}").')
        return None
    used = _hints_used(level)
    code = _code(_team, level, LEVELS[level]["hashes"][0], used)
    print(f"✅ Level {level} solved. Claim code: {code}")
    print(f"   {LEVELS[level]['solved']}")
    print(f"   Worth {points(level, used)} points ({used} hint(s) used). Submit the claim code to the game master's form.")
    return code
