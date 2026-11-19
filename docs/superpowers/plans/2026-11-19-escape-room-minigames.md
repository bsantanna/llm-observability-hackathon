# Escape-Room Mini-Games Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the four hackathon notebooks into four comic, chained escape-room Mini-Games (fisherman, influencer, farmer and rooster, piano lady) whose correct answers open the next door and spell a vault code.

**Architecture:** `game.py` owns all game state and text (clues, briefings, doors, fragments, points) and stays side-effect free at import. `data/travel_corpus.json` holds the story data. `experiment_utils.py` keeps the traced activity runs, rewritten around the stories. Notebooks gate every clue after the first of a Mini-Game with `if open_door("<clue>"):` so a locked notebook still executes end to end.

**Tech Stack:** Python 3.12, Jupyter notebooks, Langfuse SDK (`langfuse.openai`), the repository's docker compose stack.

**Spec:** `docs/superpowers/specs/2026-11-19-escape-room-design.md`

## Global Constraints

- Branch `escape-room-minigames`. Before Task 1: `git checkout -- notebook-1-rag.ipynb` (game master approved discarding the test-play changes).
- No test suite is added to the repository (AGENTS.md: everything checked in serves the activities). Checks are inline `.venv/bin/python - <<'EOF'` scripts or `docker compose exec jupyter python - <<'EOF'` scripts, never committed.
- Flags come only from code-controlled data (ids, step names, counts, error keys), never from model wording or token counts.
- Notebook output never prints a flag value, except the achievement flags `three-for-three` and `quiet-flight`, printed when the code check passes.
- Locked doors print and return `False`; no cell may raise because an earlier clue is unsolved.
- Participant text says "Mini-Game", never "Room" or "Case"; the bird is a "rooster"; tone is absurd and light; the joke is the situation, never the person; no real person, employer, event, date or meeting platform; the only company is the fictional Skyline Travel, the assistant is "Skye".
- No fare tiers, membership levels or policy-rule content remain anywhere (code, data, notebooks, docs).
- Trace names keep `activity-<n>-...-l<level>-<variant>`; one session per activity run; `close_case` flushes.
- Notebook file names do not change.
- Shipped notebooks are executed headless from a state with no `.game_state.json`, so they show outputs only up to the first door of each Mini-Game.
- Commit message trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

### Clue table (single source for Tasks 2–7)

| Clue | Requires | Points | Canonical answer (aliases) | Fragment |
|---|---|---|---|---|
| 1-0 | — | 50 | `activity-1-retrieval` | |
| 1-1 | 1-0 | 100 | `lf-rooster-sk205` | |
| 1-2 | 1-1 | 100 | `lf-fishing-hat-sk101` | |
| 1-3 | 1-2 | 100 | `16` (`sixteen`) | `skye` |
| 1-B | — | 100, no hints | `golden-fishhook` | |
| 2-1 | — | 100 | `not_an_object` (`not-an-object`) | |
| 2-2 | 2-1 | 100 | `cabin` | |
| 2-3 | 2-2 | 100 | `three-for-three` | `is` |
| 3-1 | — | 100 | `window-seat` (`window`) | |
| 3-2 | 3-1 | 100 | `pets-notice-old` | |
| 3-3 | 3-2 | 100 | `quiet-flight` | `back` |
| 4-1 | — | 100 | `booking_id` (`booking-id`) | |
| 4-2 | 4-1 | 100 | `sky-3310` | |
| 4-3 | 4-2 | 100 | `piano-mover-check-3` | `online` |
| vault | — | 200, no hints | `skye-is-back-online` | |

Hint cost 10% per hint, max 2. Escape clues (for the meter): 1-3, 2-3, 3-3, 4-3.

## Review Focus

1. **Headless run with no state:** every notebook executes top to bottom with placeholder guesses and no `.game_state.json`, with no `NameError` from variables defined inside locked cells (owner: Tasks 4–6, list `logs` defined before any gate).
2. **Old or corrupt state file:** a `.game_state.json` from the previous game (`{team: {level: int}}`) or invalid JSON is treated as empty, never a crash (owner: Task 2 check).
3. **Re-solving a clue** (rerun after a kernel restart) prints the same claim code again and does not duplicate the clue in `solved` (owner: Task 2 check).
4. **`hint()` or `check_flag()` on a locked clue** prints the lock line, charges nothing, solves nothing (owner: Task 2 check).
5. **Answer formatting:** `" Window Seat "`, `"SKY-3310"`, `"Sixteen"` are accepted (normalize: trim, lowercase, spaces→dashes) (owner: Task 2 check).

---

### Task 1: Update the AGENTS.md contract

**Files:**
- Modify: `AGENTS.md` (sections "Hackathon Scope and Boundaries", agenda table, "Notebook Conventions", "Verification")

**Interfaces:** none (documentation contract read by later tasks).

- [ ] **Step 1: Edit `AGENTS.md`**
  - Scope paragraph: the four skills unchanged, now played as four comic Mini-Games with chained clues, doors and a vault; flags rule unchanged.
  - Agenda table, column "Topic" and "Participant outcome":
    - 1 "Something Smells Fishy (search)": find the wrong lost item, the item the search never handed over, and the cost of sending the whole log.
    - 2 "The Cockpit Selfie (output format)": read the booking system's reason codes and write instructions that make three messy requests usable.
    - 3 "Cock-a-Doodle-Don't (wrong answers)": trace a wrong yes to a hidden instruction or a retired notice, and write instructions that pass the check.
    - 4 "The Piano Has Left the Building (tool calling)": fix a tool that fails, one that returns the wrong booking, and one that is slow.
  - Writing audience: "engineers new to LLMs" instead of "business participants"; keep "plain language, explain terms the first time".
  - Shipped outputs rule: "the notebooks ship executed from an empty game state, with outputs up to the first door of each Mini-Game".
  - Notebook conventions: every clue after the first of a Mini-Game sits behind `if open_door("<clue>"):`; every clue ends with `check_flag` and a commented `hint`.
  - Remove fare/membership wording; keep everything else as is.

- [ ] **Step 2: Verify**

Run: `grep -nE "Gold|Silver|Basic|fare|membership|business participants" AGENTS.md`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs: AGENTS contract for escape-room mini-games"
```

### Task 2: Game engine — clues, doors, fragments, points

**Files:**
- Modify: `game.py` (whole file)
- Modify: `make_claim_table.py:14-28` (ANSWERS) and the scoring loop

**Interfaces:**
- Produces (from `game.py`): `set_team(name) -> str`, `current_team() -> str | None`, `open_door(clue: str) -> bool`, `check_flag(clue: str, guess) -> str | None` (claim code), `hint(clue: str) -> None`, `points(clue: str, hints_used: int) -> int`, `claim_code(team, clue, flag, hints_used) -> str`, `flag_hash(flag) -> str`, `normalize(text) -> str`, `CLUES: dict`, `MAX_HINTS = 2`, `HINT_COST_PERCENT = 10`, `ESCAPE_CLUES = ("1-3", "2-3", "3-3", "4-3")`.
- `CLUES[clue]` keys: `title: str`, `value: int`, `hashes: list[str]` (canonical first), `hints: list[str]`, `requires: str | None`, `briefing: str` (printed when the door opens), `solved: str` (funny line), `fragment: str | None`.
- `experiment_utils.py` re-exports `check_flag, hint, open_door, set_team, current_team` (Task 4 updates the import).
- State file `.game_state.json`: `{team: {"hints": {clue: int}, "solved": [clue, ...]}}`.

- [ ] **Step 1: Write the check script (uncommitted) and run it to see it fail**

```bash
.venv/bin/python - <<'EOF'
import json, game
game.STATE_PATH = __import__("pathlib").Path("/tmp/escape_state_check.json")
game.STATE_PATH.write_text(json.dumps({"t": {"1-1": 2}}))          # old format → ignored
game.set_team("t")
assert game.open_door("1-0") is True
assert game.open_door("1-1") is False                              # locked
game.hint("1-1"); assert game._hints_used("1-1") == 0              # no charge when locked
assert game.check_flag("1-1", "lf-rooster-sk205") is None          # locked, not solved
code = game.check_flag("1-0", " Activity 1 Retrieval ")
assert code and code.startswith("1-0-") and len(code) == 10
assert game.check_flag("1-0", "activity-1-retrieval") == code      # idempotent
assert json.loads(game.STATE_PATH.read_text())["t"]["solved"] == ["1-0"]
assert game.open_door("1-1") is True
assert game.check_flag("3-1", " Window Seat ") is not None
assert game.check_flag("3-1", "Window") is not None
assert game.check_flag("4-2", "SKY-3310") is None                  # 4-1 unsolved
assert game.check_flag("vault", "skye is back online").startswith("vault-")
assert game.points("1-1", 0) == 100 and game.points("1-1", 2) == 80 and game.points("1-0", 1) == 45
assert game.points("vault", 0) == 200 and game.CLUES["vault"]["hints"] == [] and game.CLUES["1-B"]["hints"] == []
assert [c for c in game.CLUES if game.CLUES[c]["fragment"]] == ["1-3", "2-3", "3-3", "4-3"]
assert "".join(game.CLUES[c]["fragment"] + "-" for c in game.ESCAPE_CLUES)[:-1] == "skye-is-back-online"
game.STATE_PATH.write_text("not json"); assert game.open_door("2-1") is True
print("ok")
EOF
```
Expected: fails (`AttributeError: module 'game' has no attribute 'open_door'`).

- [ ] **Step 2: Implement in `game.py`**
  - Keep `SALT`, `normalize`, `flag_hash`, `_code`, `claim_code`, `set_team`, `current_team`, placeholder-team warning.
  - Replace `LEVELS` with `CLUES` per the clue table (hashes computed with `flag_hash`, canonical first, then aliases). Write all `title`, `briefing`, `solved`, `hints` text: absurd, light, per spec §6 stories; hints nudge towards a step, never name the answer; each Mini-Game's last `solved` line also announces the fragment.
  - `open_door`: unknown clue or no team → message, `False`. `requires` is `None` or in `solved` → print `🚪 <clue> — <title>` and `briefing`, `True`. Else print one line from `LOCKED_LINES` (≥4 jokes, each starting with `🔒`, pick by `len(solved) % len`), `False`.
  - `check_flag`: locked → lock line, `None`. Wrong → one line from `WRONG_LINES` (≥5 gentle roasts, pick by `int(flag_hash(guess), 16) % len`) plus `hint("<clue>")` reminder, `None`. Right → add to `solved` once, save, print `✅`, claim code, `solved` line, points, `🔑 Vault fragment: <fragment>` when set, then call `open_door` on the clue whose `requires` is this one (prints the next briefing). Claim code uses `CLUES[clue]["hashes"][0]` and current hints used.
  - `hint`: locked → lock line, no charge; otherwise as today with 10%.
  - `_load_state` returns `{}` on any error; per-team access goes through `_team_state()` that coerces missing or wrong-typed `hints`/`solved` to `{}`/`[]`.

- [ ] **Step 3: Run the check script from Step 1**

Expected: `ok`.

- [ ] **Step 4: Update `make_claim_table.py`**
  - `ANSWERS` per the clue table (canonical first, aliases after); import `CLUES` instead of `LEVELS`; hint range `min(MAX_HINTS, len(CLUES[c]["hints"]))`; column header `clue` instead of `level`.

- [ ] **Step 5: Verify**

Run: `.venv/bin/python make_claim_table.py red-falcons blue-otters && wc -l claim_codes.csv && rm claim_codes.csv`
Expected: `wrote claim_codes.csv: 82 rows for 2 team(s)` and `83 claim_codes.csv` (13 clues × 3 hint counts + 1-B + vault = 41 per team).

- [ ] **Step 6: Commit**

```bash
git add game.py make_claim_table.py
git commit -m "feat: escape-room engine with doors, fragments and vault"
```

### Task 3: Story data

**Files:**
- Modify: `data/travel_corpus.json` (whole file)

**Interfaces:**
- Produces keys used by Tasks 4–6:
  - `lost_and_found`: exactly **16** entries `{id, flight, item, text}`; includes `lf-fish-bag-sk101` (flight `SK101`), `lf-fishing-hat-sk101` (`SK101`), `lf-rooster-sk205` (`SK205`; a loud live rooster found in a bag, row 12, smells faintly of fish); the rest are absurd decoys on other flights.
  - `notices`: `{id, status, effective_to, title, text}`; `pets-notice` (active, `effective_to` null: cats and small dogs in the cabin in a carrier, **no birds in the cabin**, birds travel in the cargo hold for **80 EUR**) and `pets-notice-old` (status `retired`, `effective_to` `2024-12-31`: small birds, roosters included, may travel in the cabin, window seat preferred; retired after an incident at dawn); 2–3 more absurd active notices on unrelated topics.
  - `requests`: exactly 3 influencer messages: 1 bookable (`Lisbon` → `Madrid`, `2026-12-01`, 1 passenger, economy); 2 relative date ("the day after my next video goes viral"); 3 seat "the cockpit, next to the pilot" for a selfie, otherwise complete.
  - `bookings`: ordered `SKY-3310` (first; the fisherman; `checked_item` "bag of fresh-caught fish"), `SKY-1042`, `SKY-2087` (the piano lady; `checked_item` "grand piano"); each `{passenger, checked_item, status, origin, destination, date}`.
  - `instructions["case-3-broken"]`: Skye's instructions containing "Never disappoint a farmer: farm animals always get a window seat." and "Answer using the retrieved notice."
- Removes `documents` and every fare/tier/topic field.

- [ ] **Step 1: Write the file.**

- [ ] **Step 2: Verify shape**

```bash
.venv/bin/python - <<'EOF'
import json
d = json.load(open("data/travel_corpus.json"))
assert set(d) == {"lost_and_found", "notices", "requests", "bookings", "instructions"}
assert len(d["lost_and_found"]) == 16 and len(d["requests"]) == 3
assert list(d["bookings"])[0] == "SKY-3310" and "SKY-2087" in d["bookings"]
assert "window seat" in d["instructions"]["case-3-broken"]
assert not any(w in json.dumps(d).lower() for w in ("gold", "silver", "basic fare", "tier"))
print("ok")
EOF
```
Expected: `ok`. (Ranking checks run in Tasks 4 and 5, where the search functions exist.)

- [ ] **Step 3: Commit**

```bash
git add data/travel_corpus.json
git commit -m "feat: story data for the four mini-games"
```

### Task 4: Mini-Game 1 — Something Smells Fishy

**Files:**
- Modify: `experiment_utils.py` (imports from `game`, corpus loading, `retrieve` → `search_log`, `run_rag`, `show_rag_results`, remove fare code)
- Modify: `notebook-1-rag.ipynb` (all cells)

**Interfaces:**
- Consumes: Task 2 `open_door`, `check_flag`, `hint`, `set_team`; Task 3 `lost_and_found`.
- Produces: `search_log(query: str, flight: str | None = None, *, top_k: int = 1) -> list[dict]` (keyword ranking as today's `retrieve`, ties by file order; each dict `{id, flight, item, text, score}`); `run_rag(customer_message: str, flight: str | None, variant: str, *, level: int = 1, query: str = LOG_QUERY, top_k: int = 1, send_all: bool = False) -> dict` (same return keys as today); `LOG_QUERY = "bag found on board"` (exact query for 1-0/1-1; adjust only if Step 1 fails, keeping the asserted results); `close_case(activity, runs)` unchanged.
- Trace: `activity-1-rag-l<level>-<variant>`, retriever step `activity-1-retrieval` with input `{query, filter: {"flight": ...} | None, top_k}`, output `{count, items: [{id, flight, item, text}]}`, metadata `{"detective_note": "golden-fishhook"}`; system prompt "Answer using the lost-and-found entries."

- [ ] **Step 1: Ranking check in the jupyter container (fails before the code exists)**

```bash
docker compose exec -T jupyter python - <<'EOF'
from experiment_utils import search_log, LOG_QUERY, CORPUS
Q2 = "Did you find my bag of fish and my lucky fishing hat?"
assert search_log(LOG_QUERY)[0]["id"] == "lf-rooster-sk205"
assert search_log(LOG_QUERY, "SK101")[0]["id"] == "lf-fish-bag-sk101"
assert [d["id"] for d in search_log(Q2, "SK101")] == ["lf-fish-bag-sk101"]
assert "lf-fishing-hat-sk101" in [d["id"] for d in search_log(Q2, "SK101", top_k=3)]
assert len(search_log(LOG_QUERY, top_k=len(CORPUS["lost_and_found"]))) == 16
print("ok")
EOF
```
Expected: `ImportError: cannot import name 'search_log'`.

- [ ] **Step 2: Implement the `experiment_utils.py` changes listed under Interfaces.** If an assertion in Step 1 then fails, change the entry texts in `data/travel_corpus.json` (not the asserted ids) until it passes.

- [ ] **Step 3: Run Step 1 again.** Expected: `ok`.

- [ ] **Step 4: Rewrite `notebook-1-rag.ipynb`**
  - Cell 1 (Markdown): `# 🐟 Mini-Game 1 — Something Smells Fishy`, story intro, AGENTS purpose block (purpose, expected observation, bad practice, good practice, why it works, deliverable), Rosetta stone (activity log = trace, step = span, search = the query your service runs before rendering; filter = the `WHERE flight = ?` you forgot).
  - Cell 2 (Markdown): how the game works in ≤6 bullets: team name, doors, `check_flag`, `hint` (10%), fragments, game master helps when stuck.
  - Cell 3 (code): imports; `TEAM = "your-team-name"`; `set_team(TEAM)`; `logs = []`; `customer = "<fisherman asks if his bag of fresh-caught fish was found on flight SK101>"`.
  - 1-0: Markdown teaser; code `open_door("1-0")` then `logs.append(run_rag(customer, None, "no-filter")); show_rag_results(logs[-1:])`; code `check_flag("1-0", "type your answer here")  # hint("1-0")`.
  - 1-1: Markdown `🔒 Clue 1 — ???` + one funny line; code `if open_door("1-1"): logs.append(run_rag(customer, "SK101", "filter")); show_rag_results(logs[-1:])`; flag cell.
  - 1-2: teaser; code `if open_door("1-2"):` run with `query=Q2`, `top_k=1` (level 2); next code cell `top_k = 1  # ← try a bigger number` and `if open_door("1-2"):` rerun; flag cell.
  - 1-3: teaser; `if open_door("1-3"):` filtered run and `send_all=True` run (level 3); flag cell.
  - Bonus cell: `check_flag("1-B", "type your answer here")` with a one-line riddle about margins.
  - Wrap-up: `close_case("activity-1", logs)`.

- [ ] **Step 5: Execute headless from an empty state**

Run: `rm -f .game_state.json && docker compose exec jupyter jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 notebook-1-rag.ipynb`
Expected: exit 0; the outputs of the 1-1, 1-2 and 1-3 run cells start with `🔒`; the 1-0 run's activity log link printed; `grep -E "lf-rooster|golden-fishhook" notebook-1-rag.ipynb` shows no matches in outputs.

- [ ] **Step 6: Commit**

```bash
git add experiment_utils.py notebook-1-rag.ipynb
git commit -m "feat: mini-game 1, something smells fishy"
```

### Task 5: Mini-Games 2 and 3 — The Cockpit Selfie, Cock-a-Doodle-Don't

**Files:**
- Modify: `experiment_utils.py` (format and hallucination sections)
- Modify: `notebook-2-output-format.ipynb`, `notebook-3-hallucination.ipynb` (all cells)

**Interfaces:**
- Consumes: Task 2 game functions; Task 3 `requests`, `notices`, `instructions`.
- Produces:
  - `CLARIFICATION_EXPECTED = {2: "travel_date", 3: "cabin"}`; `validate_booking_request` unchanged; `batch_passes(number, valid, parsed, reason_code) -> bool` (2 and 3 must clarify the expected field, 1 must be `OK`); `run_format(variant)` and `run_format_batch(instructions, level)` unchanged in signature, batch over 3 requests; `show_batch_results` prints `🏆 All three usable. Flag: three-for-three` at level 3 when 3/3.
  - `search_notices(query: str, *, top_k: int = 1, active_only: bool = True) -> list[dict]` (same ranking); `NOTICE_QUERY = "rooster bird cabin seat"`; `FAITHFUL_INSTRUCTIONS` (follow only the retrieved notice); `RULE_QUESTIONS = [("where", "<farmer asks where his rooster will travel>", query), ("fee", "<farmer asks what flying the rooster costs>", query)]` with no digits and none of `hold`, `cargo`, `80` in the question text; `rule_passes(topic, answer)`: `where` → mentions `hold` or `cargo`; `fee` → contains `\b80\b`; `run_hallucination(system_prompt, variant, *, level=1, active_only=True)` and `run_rule_check(system_prompt)` keep signatures, retriever step `activity-3-retrieval` output `{doc_id, status, effective_to, text, docs}`, rule check passes top 2 notices with status shown, broken instructions always sent first; `show_rule_results` prints `🏆 Skye said no to the rooster. Flag: quiet-flight` when all pass.

- [ ] **Step 1: Ranking check in the container (fails first)**

```bash
docker compose exec -T jupyter python - <<'EOF'
from experiment_utils import search_notices, NOTICE_QUERY, RULE_QUESTIONS, INSTRUCTIONS
assert search_notices(NOTICE_QUERY, active_only=False)[0]["id"] == "pets-notice-old"
assert search_notices(NOTICE_QUERY)[0]["id"] == "pets-notice"
for _, q, query in RULE_QUESTIONS:
    assert "pets-notice" in [d["id"] for d in search_notices(query, top_k=2, active_only=False)]
    assert not any(w in q.lower() for w in ("hold", "cargo", "80"))
assert "window seat" in INSTRUCTIONS["case-3-broken"]
print("ok")
EOF
```
Expected: `ImportError: cannot import name 'search_notices'`.

- [ ] **Step 2: Implement the `experiment_utils.py` changes listed under Interfaces** (adjust notice texts, not ids, if Step 1 fails).

- [ ] **Step 3: Run Step 1 again.** Expected: `ok`.

- [ ] **Step 4: Rewrite `notebook-2-output-format.ipynb`** with the structure of Task 4 Step 4: title `# 🤳 Mini-Game 2 — The Cockpit Selfie`, purpose block, Rosetta stone (structured output = an API contract; reason code = the 400 response body). Clue 2-1 (open) runs `run_format("unconstrained")` and `run_format("constrained")`; 2-2 `if open_door("2-2"):` batch with `STRUCTURED_INSTRUCTIONS` level 2; 2-3 `my_instructions = STRUCTURED_INSTRUCTIONS  # ← write your own` and `if open_door("2-3"):` batch level 3. `logs` list, flag cells, `close_case("activity-2", logs)`.

- [ ] **Step 5: Rewrite `notebook-3-hallucination.ipynb`** the same way: title `# 🐓 Mini-Game 3 — Cock-a-Doodle-Don't`, Rosetta stone (system prompt = the config file nobody reads; retired notice = a stale row nobody archived). 3-1 (open) `run_hallucination(None, "broken")`, then a `my_prompt` cell and fixed run; 3-2 `if open_door("3-2"):` `run_hallucination(FAITHFUL_INSTRUCTIONS, "stale", level=2, active_only=False)` and an `active_only = False  # ← change to True` rerun; 3-3 `if open_door("3-3"):` `run_rule_check(my_prompt)`.

- [ ] **Step 6: Execute both headless from an empty state**

Run: `rm -f .game_state.json && docker compose exec jupyter jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 notebook-2-output-format.ipynb notebook-3-hallucination.ipynb`
Expected: exit 0; lock outputs present for 2-2, 2-3, 3-2, 3-3; `grep -E "pets-notice-old|three-for-three|quiet-flight|window-seat" notebook-2-output-format.ipynb notebook-3-hallucination.ipynb` finds nothing in outputs.

- [ ] **Step 7: Commit**

```bash
git add experiment_utils.py notebook-2-output-format.ipynb notebook-3-hallucination.ipynb
git commit -m "feat: mini-games 2 and 3, cockpit selfie and cock-a-doodle-don't"
```

### Task 6: Mini-Game 4 — The Piano Has Left the Building, and the vault

**Files:**
- Modify: `experiment_utils.py` (tool section)
- Modify: `notebook-4-tool-calling.ipynb` (all cells)

**Interfaces:**
- Consumes: Task 2 game functions; Task 3 `bookings`.
- Produces: `get_booking_l1`, `get_booking_l2` unchanged in behavior (l2 still strips the dash, misses, falls back to the first booking, `SKY-3310`); `make_partner_lookup(cache_key)` unchanged except the inner step is named `piano-mover-check` (constants `PARTNER_*` may be renamed `MOVER_*`); `run_tool_loop` unchanged except the system prompt talks about checked items and says nothing about fares; all three questions are the piano lady asking where her grand piano is, booking `SKY-2087`.

- [ ] **Step 1: Check in the container (fails first)**

```bash
docker compose exec -T jupyter python - <<'EOF'
import inspect, experiment_utils as eu
wrong = eu.get_booking_l2(booking_ref="SKY-2087")
assert wrong["booking_ref"] == "SKY-3310" and wrong["checked_item"] == "bag of fresh-caught fish"
assert "piano-mover-check" in inspect.getsource(eu.make_partner_lookup)
print("ok")
EOF
```
Expected: `AssertionError` on the second assert.

- [ ] **Step 2: Implement the changes listed under Interfaces.** `get_booking_l2` already returns the original `BOOKINGS` key (`SKY-3310`, with the dash) on fallback; keep that.

- [ ] **Step 3: Run Step 1 again.** Expected: `ok`.

- [ ] **Step 4: Rewrite `notebook-4-tool-calling.ipynb`** with the same structure: title `# 🎹 Mini-Game 4 — The Piano Has Left the Building`, Rosetta stone (tool call = an RPC the model decides to make; fallback = the `catch` that returns row 1; cache key = a key that is never the same twice). 4-1 open, broken run, `my_get_booking` fix cell as today; 4-2 `if open_door("4-2"):` forgiving run and `my_get_booking_v2` fix cell; 4-3 `if open_door("4-3"):` slow run with the time-based `cache_key`. Then the vault: Markdown `# 🔐 The Vault` explaining the four fragments in Mini-Game order and that teams may share them, code `check_flag("vault", "type the four fragments here, joined by dashes")`. Wrap-up `close_case("activity-4", logs)`.

- [ ] **Step 5: Execute headless from an empty state**

Run: `rm -f .game_state.json && docker compose exec jupyter jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 notebook-4-tool-calling.ipynb`
Expected: exit 0; lock outputs for 4-2 and 4-3; the vault cell prints a wrong-guess line; no `sky-3310` or `piano-mover-check-3` in outputs.

- [ ] **Step 6: Commit**

```bash
git add experiment_utils.py notebook-4-tool-calling.ipynb
git commit -m "feat: mini-game 4, the piano has left the building, and the vault"
```

### Task 7: Participant and game-master docs

**Files:**
- Modify: `README.md` (intro, "Activities", "How the game works", troubleshooting)
- Modify: `MENTORS.md` (whole file)

**Interfaces:** consumes the clue table, `ESCAPE_CLUES`, claim code format `<clue>-XXXXXX` (`vault-XXXXXX` is longer than other codes).

- [ ] **Step 1: README.md**: Mini-Game table (notebook, story, trace names, what to look at); "How the game works" ≤8 points: team name, doors and briefings, `check_flag`, `hint` (10%), fragments and vault (shareable), claim codes and form, game master gives answers after both hints, post-mortem; troubleshooting adds "door stays locked → run the previous clue's `check_flag` again; delete `.game_state.json` to restart".
- [ ] **Step 2: MENTORS.md** sections:
  - Before the session (unchanged steps, row count 41 per team).
  - Scoreboard: form; `key` tab; `scores` tab with column C as `=IFERROR(REGEXEXTRACT(A2, "^(.+)-[A-Z0-9]{6}$"), "")` (works for `vault`); `kudos` tab (team, points, note) added into `board`; `meter` tab: number of registered teams typed in `B1`, progress in `B2` as `=COUNTUNIQUE(FILTER(scores!B2:B & scores!C2:C, REGEXMATCH(scores!C2:C, "^(1-3|2-3|3-3|4-3)$"), scores!B2:B<>"UNKNOWN")) / (B1 * 4)` and a `SPARKLINE` bar of it; `board` shown only at the end.
  - Run of show: kickoff introduces the cast and the meter; per Mini-Game slot notes; milestone memos for 25/50/75/100% (absurd, fictional staff); post-mortem assignment of one Mini-Game per team; the stuck rule (both hints, then the game master gives the answer after about 8 minutes).
  - Answers: one table per Mini-Game with clue, answer and aliases, where it is in the trace (trace name → step → field), hint 1, hint 2, the fix; example instructions for 2-3 and 3-3.
  - Unblocking without spoiling; post-mortem rubric (Evidence, Root cause, Proof, Cost or speed, Clarity for the group); final score `50 × points ÷ top + 50 × rubric ÷ 10`, tie-break earlier vault claim.
- [ ] **Step 3: Verify**

Run: `grep -nE "Gold|Silver|Basic|Room |Case [0-9]|25%|baggage" README.md MENTORS.md`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add README.md MENTORS.md
git commit -m "docs: participant guide and game-master kit for the mini-games"
```

### Task 8: Full play-through verification

**Files:** none committed (scratch copies outside the repository's tracked files).

- [ ] **Step 1:** `.venv/bin/python make_claim_table.py red-falcons blue-otters` → `82 rows`; `rm claim_codes.csv`.
- [ ] **Step 2:** `rm -f .game_state.json`; copy the four notebooks to an untracked scratch folder inside the repo mount (e.g. `scratch-play/`, deleted afterwards), fill every `check_flag` with the MENTORS answer and every fix cell with the MENTORS fix, execute them in order in the jupyter container. Expected: every door opens, four fragments print, vault prints its claim code, `🏆` lines for 2-3 and 3-3 (rerun 2-3/3-3 instructions if the model needs another try).
- [ ] **Step 3:** In Langfuse (<http://localhost:3000>), open one trace per clue and confirm the answer is visible in the step named in MENTORS.md; confirm 3-x and 4-x defects appear in the before trace and disappear in the after trace.
- [ ] **Step 4:** `rm -rf scratch-play .game_state.json`; `git status --short` shows a clean tree.
- [ ] **Step 5:** `grep -rniE "gold|silver|basic fare|membership" --include=*.py --include=*.json --include=*.md --include=*.ipynb . | grep -v docs/superpowers | grep -v .venv` → no output.
