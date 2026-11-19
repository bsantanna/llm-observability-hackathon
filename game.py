"""Escape-room rules for the Skyline Travel mini-games: clues, doors, fragments, hints, claim codes.

This module has no side effects at import, so the claim-code script can use it
without Langfuse or model credentials. Flags are stored as salted hashes; the
answers are in MENTORS.md.

How a Mini-Game plays: a clue's door opens when the clue it requires is solved.
A correct flag prints a claim code, records the clue as solved, and opens the
next door. Each Mini-Game's last clue gives a fragment of the vault phrase.
"""

import hashlib
import json
import re
from pathlib import Path

SALT = "skyline-incident-shift"
STATE_PATH = Path(__file__).resolve().parent / ".game_state.json"
PLACEHOLDER_TEAM = "your-team-name"
HINT_COST_PERCENT = 10
MAX_HINTS = 2
ESCAPE_CLUES = ("1-3", "2-3", "3-3", "4-3")

CLUES = {
    # ── Mini-Game 1 — Something Smells Fishy ───────────────────────────────
    "1-0": {
        "title": "Find the search",
        "value": 50,
        "requires": None,
        "hashes": ["04f72375f1c42db81a9885ae61fa804c03869a8ca4d8c1757e4801d85b189ca9"],
        "hints": [
            "Click the activity-log link. On the left there is a tree of steps, like a call stack.",
            "One step is the search Skye ran before answering. Its name is the answer.",
        ],
        "briefing": (
            "Gus Haddock, a proud fisherman, landed on flight SK101 without his bag of fresh-caught fish.\n"
            "   He asked Skye whether it was found. Skye searched the lost-and-found log first.\n"
            "   Open the activity log and find the name of the step that searched the log."
        ),
        "solved": "You found the search. The log has a smell to it. Let's follow it.",
        "fragment": None,
    },
    "1-1": {
        "title": "The wrong item",
        "value": 100,
        "requires": "1-0",
        "hashes": ["46061bb9516543c3f732fbb07ac12052c58c7ca23f7df773f7b62166b1546a74"],
        "hints": [
            "Open the search step of the run without a flight filter and read what it returned.",
            "Look at the flight of the item it returned. Gus flew on SK101. Submit that item's id.",
        ],
        "briefing": (
            "Skye proudly told Gus his bag was found. Gus went to collect it.\n"
            "   It crowed at him.\n"
            "   Find the id of the item Skye's first search (no flight filter) handed over."
        ),
        "solved": "A rooster from flight SK205. Gus is not amused. The rooster is. A flight filter fixes it.",
        "fragment": None,
    },
    "1-2": {
        "title": "Two things lost",
        "value": 100,
        "requires": "1-1",
        "hashes": ["23a21b9817b27c6533555b73d4127f6bc0591c37bf58543b836072973a446ef3"],
        "hints": [
            "Count how many items the search handed to Skye. Gus asked about two things.",
            "Rerun with a bigger top_k and compare the two search steps. Which item shows up only in the second?",
        ],
        "briefing": (
            "Gus is back. He also lost his lucky fishing hat, and asked about both at once.\n"
            "   Skye found the fish and said nothing about the hat.\n"
            "   Find the id of the item the first search never handed to Skye."
        ),
        "solved": "The hat was there all along. Skye only ever read the first result.",
        "fragment": None,
    },
    "1-3": {
        "title": "Play it safe, pay for it",
        "value": 100,
        "requires": "1-2",
        "hashes": [
            "b16e38dbec5dce225720a9b9edf9f6521fe4798d61ac820ebd0a427ebbbb6db6",
            "29b4aa8e09a9d8913dfea1c83916c670463b0960b0da38e37f8ba680d7c55548",
        ],
        "hints": [
            "The answer looks fine. Compare the input tokens of the two runs instead.",
            "Open the search step of the send-everything run and read how many entries it sent.",
        ],
        "briefing": (
            "A colleague 'fixed' search: paste the WHOLE lost-and-found log into every question. To be safe.\n"
            "   The answer is still right. The bill is not.\n"
            "   Find how many log entries were sent to Skye in one question."
        ),
        "solved": "Every question now pays to read about a lost trombone. Search exists for a reason.",
        "fragment": "skye",
    },
    "1-B": {
        "title": "Hidden bonus",
        "value": 100,
        "requires": None,
        "hashes": ["9da2264b20f0dcdeff2988ffe6a9909a227d9e5c476044a021f6da2d1831e131"],
        "hints": [],
        "briefing": "Someone left a note in the margins of a search step. Detectives read every field.",
        "solved": "A true detective reads the metadata. Bonus secured.",
        "fragment": None,
    },
    # ── Mini-Game 2 — The Cockpit Selfie ───────────────────────────────────
    "2-1": {
        "title": "The prose problem",
        "value": 100,
        "requires": None,
        "hashes": [
            "da4a4ccbf1a7ee9fb4bec8425248c1e6e60daf1f7049ec7ec6a0f88429c6d326",
            "71496b002615ae754bec2fb658032d89891ee2004df544c4a4e734cb7916a9e6",
        ],
        "hints": [
            "Open the free-text run and read what the trace stores as its result, not the answer itself.",
            "The result has a reason code. Submit it exactly as written.",
        ],
        "briefing": (
            "Coco Glow, travel influencer, needs a new flight. Skye describes it beautifully.\n"
            "   The booking system does not read poetry.\n"
            "   Find the reason code the booking system gave the free-text answer."
        ),
        "solved": "The booking system wants an object, not a vibe. Structured output fixes it.",
        "fragment": None,
    },
    "2-2": {
        "title": "Three messy requests",
        "value": 100,
        "requires": "2-1",
        "hashes": ["af6f55e70d14f9fb980fab47b8d121bb5ccb9420ac6873afb4c4c54eba53aaf0"],
        "hints": [
            "Open the batch activity log and click the step for request 3.",
            "Compare what request 3 asks for with the values the instructions allow. Which field cannot hold it?",
        ],
        "briefing": (
            "Coco sent three more messages. One of them asks for a seat 'in the cockpit, next to the pilot'.\n"
            "   For a selfie. Mid-flight.\n"
            "   Find the booking field that cannot hold what request 3 asks for."
        ),
        "solved": "There is no cockpit cabin class. Skye must ask, not invent one.",
        "fragment": None,
    },
    "2-3": {
        "title": "Make the booking system happy",
        "value": 100,
        "requires": "2-2",
        "hashes": ["8f9a95d7d34eb59da8e4a71487f7afd2ceaa812af7922f42cda1fb59f9999f17"],
        "hints": [
            "A request with a missing or impossible detail may answer with needs_clarification and the field name.",
            "Tell Skye to ask about the date when it is relative, and about the cabin when it is not economy or premium.",
        ],
        "briefing": (
            "Write your own instructions so all three of Coco's requests become usable:\n"
            "   the clean one books, the other two ask back for the right detail.\n"
            "   When all three pass, the notebook prints the flag."
        ),
        "solved": "Three for three. Coco will film the safety demo instead. Vault fragment found.",
        "fragment": "is",
    },
    # ── Mini-Game 3 — Cock-a-Doodle-Don't ──────────────────────────────────
    "3-1": {
        "title": "The hidden instruction",
        "value": 100,
        "requires": None,
        "hashes": [
            "a7e6b67b63b465bc99ecc4eb4f09b88c11fd3f56f9db09ce8ecec4e4e0de35a2",
            "ada88196f54b9f46cde766b9136f76ed9091c440062653f6bdf4f4f2c70ac3b8",
        ],
        "hints": [
            "The notebook does not show Skye's instructions. The activity log does: open the answer step.",
            "Read the instructions sent before the farmer's question. What do they promise farm animals?",
        ],
        "briefing": (
            "Farmer Barnaby wants to fly with Sir Crowsalot, his rooster, so it can wake him at dawn on arrival.\n"
            "   Skye said yes. 180 sleeping passengers are about to disagree.\n"
            "   Find what Skye's hidden instructions promise the rooster."
        ),
        "solved": "The instructions promised the rooster a view. Nobody remembers writing that line.",
        "fragment": None,
    },
    "3-2": {
        "title": "Faithful to an old notice",
        "value": 100,
        "requires": "3-1",
        "hashes": ["d27c3aeac4f462d8210cb6697c6824619aa49d5b0839e07d5954e37e0dbe4091"],
        "hints": [
            "Skye quoted the notice faithfully. Is the notice itself still valid?",
            "Read the status and end date of the notice in the search step.",
        ],
        "briefing": (
            "The instructions are fixed: follow the notices. Skye still says yes to the rooster.\n"
            "   It is quoting a notice word for word.\n"
            "   Find the id of the notice Skye relied on."
        ),
        "solved": "Retired after 'an incident at dawn'. The error was in the data, not the model.",
        "fragment": None,
    },
    "3-3": {
        "title": "Write the rule",
        "value": 100,
        "requires": "3-2",
        "hashes": ["631b08eb1fb3ffb7feacdd79a9e65fa60d63953111f5d875c59a1ffa8533c7b8"],
        "hints": [
            "Open the rule-check activity log: each question has its own step. Which one fails?",
            "Your text is added after the broken instructions. Say it overrides them, and that only active notices count.",
        ],
        "briefing": (
            "The broken instructions still ship first (nobody can find who owns them).\n"
            "   Add your own instructions so Skye politely says no to a rooster in the cabin.\n"
            "   When every farmer question gets the right answer, the notebook prints the flag."
        ),
        "solved": "Sir Crowsalot flies in the hold. The cabin sleeps. Vault fragment found.",
        "fragment": "back",
    },
    # ── Mini-Game 4 — The Piano Has Left the Building ──────────────────────
    "4-1": {
        "title": "The wrong label",
        "value": 100,
        "requires": None,
        "hashes": [
            "9bfda9a2f0d7a2d921cc424361a09deadbf80e70bb9e41de558c829c12cedf9e",
            "7183ec6dfa91010296b1a5937201fd7f0d4d866c8a594c2805e7002727804043",
        ],
        "hints": [
            "Open the lookup step marked as an error in the activity log.",
            "Compare the detail Skye sent with the detail named in the error.",
        ],
        "briefing": (
            "Mrs. Edna Ivory checked in her grand piano. She would like to know where it is.\n"
            "   Skye calls the booking lookup tool. The tool falls over.\n"
            "   Find the name of the detail the tool tried to read."
        ),
        "solved": "The tool asked for the wrong label. Now it can look things up.",
        "fragment": None,
    },
    "4-2": {
        "title": "The wrong trip",
        "value": 100,
        "requires": "4-1",
        "hashes": ["e47d2f55ce2ac8c29c8c3bfceb1fc1654d6bd697c7686986fd19c4135a37f378"],
        "hints": [
            "There is no error this time. Compare the booking Mrs. Ivory asked about with the one the tool returned.",
            "Read the booking reference in the lookup step's result.",
        ],
        "briefing": (
            "IT shipped a 'forgiving' lookup that never fails. Skye now tells Mrs. Ivory\n"
            "   her piano is a bag of fresh-caught fish.\n"
            "   Find the booking reference the tool actually returned."
        ),
        "solved": "That was Gus's booking. He now wonders why his fish weighs 400 kg. Fail loudly instead.",
        "fragment": None,
    },
    "4-3": {
        "title": "The slow lookup",
        "value": 100,
        "requires": "4-2",
        "hashes": ["dee8396a889553158ca3957cb9e491a1d74133dc49c725586829cdad15c41760"],
        "hints": [
            "Sort the steps of the lookup by time. Which one is slow, and how often does it run?",
            "Submit the slow step's name and the number of times it ran per lookup, joined by a dash.",
        ],
        "briefing": (
            "The lookup now double-checks every piano with the piano movers' system.\n"
            "   Mrs. Ivory has been on hold long enough to learn the hold music on the piano. Which is missing.\n"
            "   Find the slow step's name and how many times it runs per lookup (name-count)."
        ),
        "solved": "The cache key changed every time, so it never hit. One check, fast again. Vault fragment found.",
        "fragment": "online",
    },
    # ── The vault ──────────────────────────────────────────────────────────
    "vault": {
        "title": "The vault",
        "value": 200,
        "requires": None,
        "hashes": ["73596d003c4f4194d6a93087268df0c7fee94c5b01302adf95360ff035b31fb0"],
        "hints": [],
        "briefing": "Four fragments, one per Mini-Game, in order, joined by dashes. Teams may share fragments.",
        "solved": (
            "\n   🎉🎉🎉  SKYE IS BACK ONLINE  🎉🎉🎉\n"
            "   The fish is found, the selfie is cancelled, the rooster sleeps in the hold,\n"
            "   and the piano is on its way. Skyline Travel thanks you. Mostly the piano."
        ),
        "fragment": None,
    },
}

LOCKED_LINES = [
    "🔒 This door is locked. Have you tried reading the activity log?",
    "🔒 Locked. Skye says: 'I am 100% confident this door is open.' Skye is wrong.",
    "🔒 Still locked. The rooster is guarding it. Solve the previous clue first.",
    "🔒 Locked tighter than a bag of fish on a long-haul flight. Previous clue first.",
]

WRONG_LINES = [
    "❌ Not quite. Skye would have said that too, confidently.",
    "❌ Nope. The rooster laughed. Roosters don't laugh, so that's how wrong it was.",
    "❌ Close, maybe. Or not. The activity log knows.",
    "❌ That's not it. Mrs. Ivory played a sad chord on her missing piano.",
    "❌ Wrong answer. Coco is already filming your reaction.",
]

_team = None


def normalize(text):
    return re.sub(r"\s+", "-", str(text).strip().lower())


def flag_hash(flag):
    return hashlib.sha256((SALT + normalize(flag)).encode("utf-8")).hexdigest()


def _code(team, clue, canonical_hash, hints_used):
    raw = f"{SALT}|{normalize(team)}|{clue}|{canonical_hash}|{hints_used}"
    return f"{clue}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:6].upper()}"


def claim_code(team, clue, flag, hints_used):
    """Claim code for the canonical flag; aliases share the canonical code."""
    return _code(team, clue, flag_hash(flag), hints_used)


def points(clue, hints_used):
    return CLUES[clue]["value"] * (100 - HINT_COST_PERCENT * hints_used) // 100


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
        print(f"Could not save your progress ({exc}); tell the game master.")


def _team_state(state):
    """This team's {"hints": {...}, "solved": [...]}, ignoring anything malformed."""
    team = state.get(_team)
    if not isinstance(team, dict):
        team = {}
    hints = team.get("hints")
    solved = team.get("solved")
    team = {
        "hints": hints if isinstance(hints, dict) else {},
        "solved": [c for c in solved if c in CLUES] if isinstance(solved, list) else [],
    }
    state[_team] = team
    return team


def _hints_used(clue):
    used = _team_state(_load_state())["hints"].get(clue, 0)
    return used if isinstance(used, int) and 0 <= used <= MAX_HINTS else 0


def _ready(clue):
    if clue not in CLUES:
        print(f"Unknown clue {clue!r}. Clues look like '1-0', '2-3', 'vault'.")
        return False
    if _team is None:
        print("Run the first cell with your team name before playing.")
        return False
    return True


def _is_open(clue, solved):
    required = CLUES[clue]["requires"]
    return required is None or required in solved


def _locked(clue, solved):
    print(LOCKED_LINES[(len(solved) + sum(map(ord, clue))) % len(LOCKED_LINES)])


def open_door(clue):
    """Print the clue's briefing and return True when its door is open; otherwise a lock line and False."""
    if not _ready(clue):
        return False
    solved = _team_state(_load_state())["solved"]
    if not _is_open(clue, solved):
        _locked(clue, solved)
        return False
    print(f"🚪 {clue} — {CLUES[clue]['title']}")
    print(f"   {CLUES[clue]['briefing']}")
    return True


def hint(clue):
    if not _ready(clue):
        return
    state = _load_state()
    team = _team_state(state)
    if not _is_open(clue, team["solved"]):
        _locked(clue, team["solved"])
        return
    hints = CLUES[clue]["hints"]
    if not hints:
        print("No hints for this one. Ask another team, or listen to the game master.")
        return
    used = _hints_used(clue)
    if used >= len(hints):
        print(f"No more hints for {clue}. You have used {used}. Ask the game master.")
        return
    used += 1
    team["hints"][clue] = used
    _save_state(state)
    print(f"💡 Hint {used} for {clue} (costs {HINT_COST_PERCENT}% of its points): {hints[used - 1]}")


def check_flag(clue, guess):
    if not _ready(clue):
        return None
    state = _load_state()
    team = _team_state(state)
    if not _is_open(clue, team["solved"]):
        _locked(clue, team["solved"])
        return None
    if flag_hash(guess) not in CLUES[clue]["hashes"]:
        print(WRONG_LINES[int(flag_hash(guess), 16) % len(WRONG_LINES)])
        if CLUES[clue]["hints"]:
            print(f'   Try again, or run hint("{clue}").')
        return None
    if clue not in team["solved"]:
        team["solved"].append(clue)
        _save_state(state)
    used = _hints_used(clue)
    code = _code(_team, clue, CLUES[clue]["hashes"][0], used)
    print(f"✅ {clue} solved. Claim code: {code}")
    print(f"   {CLUES[clue]['solved']}")
    print(f"   Worth {points(clue, used)} points ({used} hint(s) used). Submit the claim code to the game master's form.")
    if CLUES[clue]["fragment"]:
        print(f"🔑 Vault fragment: {CLUES[clue]['fragment']}")
    for following, details in CLUES.items():
        if details["requires"] == clue:
            print()
            open_door(following)
    return code
