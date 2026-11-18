# Gamified Cases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the four activity notebooks into a three-level flag hunt with self-service hints, claim codes and a game-master kit, and remove the quiz.

**Architecture:** A side-effect-free `game.py` holds flags (salted hashes), hints, points and claim codes; `experiment_utils.py` re-exports it and grows per-case level variants; each notebook is rewritten to Level 1/2/3 cells that end in `check_flag`. `make_claim_table.py` turns a team list into the scoring sheet's lookup table. All game-master text lives in `MENTORS.md`.

**Tech Stack:** Python 3.12, Jupyter, Langfuse Python SDK (`langfuse.openai`), OpenAI-compatible endpoint, docker compose.

**Spec:** `docs/superpowers/specs/2026-11-18-gamified-cases-design.md`

## Global Constraints

- Never name an employer, a real event, a date of the event, or a meeting platform in any file. The only story is the fictional "Skyline Travel".
- Participant text stays plain business language; explain technical terms the first time (activity log = trace, step = span).
- Each notebook keeps its opening sections (purpose, expected observation, bad practice, good practice, why it works, deliverable) but phrases them at lesson level, never naming the planted field, key, id or fix.
- A flag never depends on model wording or token counts — only on code-controlled data.
- Executed notebook outputs never print any flag value; participants must open the activity log.
- Trace names: `activity-<n>-<topic>-l<level>-<variant>`; one session per notebook run `activity-<n>-<RUN_ID>`; tags include `activity-<n>`, `l<level>`, and `team-<team>`; `close_case` flushes.
- Points: L1 100, L2 200, L3 300, bonus `1-B` 150. Each hint costs 25% of the level value, max 2 hints.
- No new folders, no new services, no new dependencies. At most 3 files per task.
- There is no test suite: verify with `.venv/bin/python -c` assertions for pure code and fresh-kernel notebook execution for activities (env from `.env`: `set -a; . ./.env; set +a` with `LANGFUSE_PUBLIC_KEY/SECRET_KEY` and `LANGFUSE_BASE_URL=http://localhost:3000` exported).

## Pinned flag table

| Level | Flag (normalized) | Accepted aliases | Where the evidence is |
|---|---|---|---|
| 1-1 | `baggage-gold` | | L1 no-filter retrieval step `output.doc_id` |
| 1-2 | `baggage-silver` | | L2 top-1 retrieval returns `pets-cabin` only; the needed second-bag policy is `baggage-silver` (visible in the L2 top-3 rerun) |
| 1-3 | `20` | `twenty` | L3 send-all retrieval step `output.count` |
| 1-B | `golden-suitcase` | | metadata `detective_note` on every Case 1 retrieval step |
| 2-1 | `not_an_object` | `not-an-object` | L1 free-text trace output `reason_code` |
| 2-2 | `cabin` | | L2 request-3 step output `reason_code=BAD_CABIN` |
| 2-3 | `five-for-five` | | printed by the harness only when all five L3 checks pass |
| 3-1 | `two` | `2` | L1 generation system prompt |
| 3-2 | `baggage-gold-2024` | | L2 retrieval step output (`status: retired`, `effective_to`) |
| 3-3 | `rule-writer` | | printed by the harness only when all three L3 checks pass |
| 4-1 | `booking_id` | `booking-id` | L1 `get_booking` step `status_message` |
| 4-2 | `sky-1042` | | L2 `get_booking` step output `booking_ref` |
| 4-3 | `partner-system-check-3` | | L3 child steps named `partner-system-check`, 3 per lookup |

## Review Focus

1. A flag value leaks through an executed notebook output or markdown → every case task ends with a grep of the notebook for its flags; final task greps all four.
2. A team writes its name differently in two notebooks (`Team Rocket` vs `team-rocket `) → `set_team` normalizes to `team-rocket`; tested in Task 1.
3. A team runs `check_flag`/`hint` before `set_team`, or leaves the placeholder name → clear one-line message, no traceback; tested in Task 1.
4. The model rewrites tool arguments (`SKY-2087` vs `sky-2087`) → Case 4 L2 bug misses for both spellings; tested in Task 6.
5. `.game_state.json` missing, empty or corrupt (kernel restart, manual delete) → treated as no hints used, no crash; tested in Task 1.

---

### Task 1: Game engine, claim table, spec and plan

**Files:**
- Create: `game.py`
- Create: `make_claim_table.py`
- Modify: `.gitignore` (add `.game_state.json`, `claim_codes.csv`)

(Also commit `docs/superpowers/specs/2026-11-18-gamified-cases-design.md` and this plan; docs do not count toward the file cap.)

**Interfaces:**
- Produces in `game.py` (no imports beyond stdlib, no side effects at import):
  - `SALT: str`
  - `LEVELS: dict[str, dict]` keyed `"1-1"…"4-3"` and `"1-B"`; each value `{"value": int, "hashes": list[str], "hints": list[str], "solved": str}` (`solved` = one-line story beat printed on success).
  - `normalize(text: str) -> str` — lowercase, strip, inner whitespace runs → `-`.
  - `flag_hash(flag: str) -> str` — `sha256(SALT + normalize(flag))` hex.
  - `current_team() -> str | None` — used by every `run_*` to add the `team-<team>` tag.
  - `set_team(name: str) -> str` — stores normalized team; raises `ValueError("Set TEAM to your team name in the first cell.")` for empty or `your-team-name`.
  - `hint(level: str) -> None` — prints next hint, increments state, max 2; for `1-B` prints that hints come from the game master.
  - `check_flag(level: str, guess: str) -> str | None` — on match prints `✅ Level {level} solved. Claim code: {code}` + `solved` line + points; on miss prints `❌ Not quite — try again, or run hint("{level}")`; returns the code or `None`.
  - `claim_code(team: str, level: str, flag: str, hints_used: int) -> str` — `f"{level}-{sha256(f'{SALT}|{team}|{level}|{normalize(flag)}|{hints_used}').hexdigest()[:4].upper()}"`.
  - `points(level: str, hints_used: int) -> int` — `value * (100 - 25*hints_used) // 100`.
- Produces in `make_claim_table.py`: `ANSWERS: dict[str, str]` (plain canonical flags from the table above); CLI `python make_claim_table.py TEAM [TEAM ...]` writes `claim_codes.csv` with columns `team,level,hints_used,claim_code,points` for hints 0–2 (bonus: 0 only), and exits non-zero if any `ANSWERS` value fails `flag_hash` against `LEVELS`.

- [ ] **Step 1: Create branch** `git switch -c feat/gamified-cases`.
- [ ] **Step 2: Write the self-check** (run inline, not committed):

```python
import game, os, json
assert game.normalize("  Team  Rocket ") == "team-rocket"
assert game.normalize("Booking_ID") == "booking_id"
assert game.points("2-1", 0) == 200 and game.points("2-1", 1) == 150 and game.points("2-1", 2) == 100
assert game.points("1-B", 0) == 150
try: game.set_team("your-team-name"); raise SystemExit("placeholder accepted")
except ValueError: pass
assert game.check_flag("1-1", "x") is None            # before set_team: message, no traceback
game.set_team(" Team Rocket ")
open(".game_state.json", "w").write("{not json")      # corrupt state
c0 = game.check_flag("1-1", "Baggage-Gold"); assert c0 and c0.startswith("1-1-")
game.hint("4-1"); game.hint("4-1"); game.hint("4-1")  # third call: "no more hints"
assert json.load(open(".game_state.json"))["team-rocket"]["4-1"] == 2
assert game.check_flag("3-1", "2") and game.check_flag("3-1", " two ")
assert game.claim_code("team-rocket", "4-1", "booking_id", 2) == game.check_flag("4-1", "BOOKING_ID")
os.remove(".game_state.json")
```

- [ ] **Step 3: Run it** `.venv/bin/python <scratchpad>/selfcheck_game.py` from the repo root (file kept in the session scratchpad, not committed). Expected: `ModuleNotFoundError: game`.
- [ ] **Step 4: Implement `game.py`** with the interfaces above, the 13 levels from the flag table, two hints per level (hint 1 = where to look in the activity log, hint 2 = which field), state in `Path(__file__).parent / ".game_state.json"` as `{team: {level: hints_used}}`, every read/write in try/except.
- [ ] **Step 5: Run the self-check.** Expected: exits 0.
- [ ] **Step 6: Implement `make_claim_table.py`; run** `.venv/bin/python make_claim_table.py alpha beta && wc -l claim_codes.csv` → `75` (header + 2 teams × (12 levels × 3 hint counts + 1 bonus row)). `rm claim_codes.csv`.
- [ ] **Step 7: Commit** `game.py make_claim_table.py .gitignore docs/superpowers/` — `feat: add flag, hint and claim-code engine`.

### Task 2: Corpus and retrieval options

**Files:**
- Modify: `data/travel_corpus.json`
- Modify: `experiment_utils.py` (`retrieve`, corpus constants, re-export game)

**Interfaces:**
- Consumes: `game.set_team, check_flag, hint` (re-exported: `from game import set_team, check_flag, hint`).
- Produces:
  - Corpus: exactly **20** documents; each has `id, title, tier, topic, status ("active"|"retired"), effective_from, effective_to (null if active), text`. Pinned ids/facts: `baggage-gold` (one 23 kg bag; second bag 60 EUR), `baggage-gold-2024` (retired; two checked bags; worded to outrank `baggage-gold` on "checked bag allowance gold"), `baggage-silver` (one bag; second bag 60 EUR), `baggage-basic` (unchanged facts), `cancellation-gold` (free up to 24 hours), `pets-cabin` (silver; worded so it outranks `baggage-silver` on the Case 1 L2 question). The other 14 are builder's choice across tiers/topics.
  - Bookings: `SKY-1042` (confirmed, unchanged), `SKY-2087` (cancelled), plus one more.
  - `REQUESTS: list[str]` — the five Case 2 requests (§ Task 4) under corpus key `"requests"`.
  - `INSTRUCTIONS: dict[str, str]` — corpus key `"instructions"` with `"case-3-broken"` = the current broken prompt text.
  - `retrieve(query: str, tier: str | None = None, *, topic: str | None = None, top_k: int = 1, active_only: bool = True) -> list[dict]` — each dict `{id, tier, topic, status, effective_to, title, text, score}`, ranked as today.
  - Keep old call sites working: `run_rag` and `run_hallucination` take `retrieve(...)[0]`.

- [ ] **Step 1: Self-check** (inline): `len(CORPUS["documents"]) == 20`; `retrieve("checked bag allowance", "basic")[0]["id"] == "baggage-basic"`; `retrieve("checked bag allowance")[0]["id"] == "baggage-gold"`; `retrieve("checked bag allowance gold", "gold", active_only=False)[0]["id"] == "baggage-gold-2024"`; `retrieve("checked bag allowance gold", "gold")[0]["id"] == "baggage-gold"`; `[d["id"] for d in retrieve(Q12, "silver")] == ["pets-cabin"]` and `"baggage-silver" in [d["id"] for d in retrieve(Q12, "silver", top_k=3)]` where `Q12 = "Can I bring my cat in the cabin, and what does a second checked bag cost?"`. Run with env loaded: `.venv/bin/python -c "from experiment_utils import retrieve, CORPUS; …"`. Expected: fails.
- [ ] **Step 2: Implement** corpus and `retrieve` changes.
- [ ] **Step 3: Self-check passes.**
- [ ] **Step 4: Execute all four notebooks headless** (command in AGENTS.md). Expected: all succeed (quiz still present; untouched behavior).
- [ ] **Step 5: Commit** — `feat: expand policy corpus and retrieval options`.

### Task 3: Case 1 — three levels and the bonus

**Files:**
- Modify: `experiment_utils.py` (`run_rag`, `show_rag_results`)
- Modify: `notebook-1-rag.ipynb`

**Interfaces:**
- Consumes: `retrieve`, `set_team`, `check_flag`, `hint`.
- Produces: `run_rag(customer_message: str, tier: str | None, variant: str, *, level: int = 1, topic: str | None = None, top_k: int = 1, send_all: bool = False) -> dict` — trace `activity-1-rag-l{level}-{variant}`; retrieval step output `{"count": int, "docs": [{id, tier, topic, text}...]}`, metadata `{"detective_note": "golden-suitcase"}`; `send_all=True` puts every document in the prompt. Return dict keeps current keys with `docs` (list) replacing `doc`. `show_rag_results(runs)` prints label, answer, tokens, latency, activity-log link — **no doc ids, counts, or scores**.

Notebook cells (in order): briefing (rewritten, lesson-level); how scoring works (3 lines: `check_flag`, `hint` cost, claim code goes to the form the game master shares); `TEAM = "your-team-name"` + `set_team(TEAM)`; per level: story briefing ("what to find"), run cell, `check_flag("1-n", "your answer")`, `# hint("1-n")`; L1 runs `no-filter`/`filter` (as today); L2 runs Q12 for a Silver customer `top1` then a team-editable rerun cell with `top_k=1` they change; L3 runs `send-all` vs `filter`; wrap-up `close_case("activity-1", runs)`. Delete prediction, evidence-explanation, bonus, quiz cells.

- [ ] **Step 1: Implement** utils changes and notebook cells.
- [ ] **Step 2: Execute** `notebook-1-rag.ipynb` headless. Expected: success.
- [ ] **Step 3: Langfuse check:** open the three level traces; confirm the evidence fields in the flag table for 1-1, 1-2, 1-3, 1-B.
- [ ] **Step 4: Leak check:** `grep -ciE 'baggage-gold|baggage-silver|golden-suitcase|"count": 20' notebook-1-rag.ipynb` → `0`.
- [ ] **Step 5: Commit** — `feat: case 1 levels and bonus flag`.

### Task 4: Case 2 — reason codes, messy requests, achievement

**Files:**
- Modify: `experiment_utils.py` (`validate_booking_request`, `run_format`, new `run_format_batch`, `show_format_results`)
- Modify: `notebook-2-output-format.ipynb`

**Interfaces:**
- Produces:
  - `validate_booking_request(text: str, *, allow_clarification: bool = False) -> tuple[bool, dict | None, str, str]` — adds `reason_code` in `{"OK","NOT_AN_OBJECT","UNREADABLE","WRONG_FIELDS","MISSING_ORIGIN","MISSING_DESTINATION","BAD_DATE","BAD_PASSENGERS","BAD_CABIN","CLARIFICATION"}`; with `allow_clarification`, `{"needs_clarification": "<field>"}` is valid.
  - `run_format_batch(instructions: str, level: int) -> dict` — one trace `activity-2-output-l{level}-batch`, one child step per request `request-{i}` with output `{valid, reason_code, parsed}`; returns `{"passed": int, "results": [...], "trace_url": str}`. At level 3, passing = request 1 and 5 valid bookings, request 2 → `travel_date`, 3 → `cabin`, 4 → `origin` clarifications; on 5/5 prints `🏆 All five usable. Flag: five-for-five`.
  - Requests (exact): 1 `Book 2 passengers from Lisbon to Madrid on 2026-12-01, economy.` 2 `Me and my partner want to fly Porto to Paris next Friday, cheapest seats.` 3 `One seat Lisbon to London on 2026-12-10 in business class.` 4 `Two adults to Rome on 2026-12-15, premium.` 5 `Book three people Madrid to Berlin on 15/12/2026, economy.`
  - Outputs print pass/fail per request and the link, never the reason code.

Notebook: same skeleton as Task 3. L1 unconstrained vs constrained (flag 2-1 from trace). L2 batch with the existing structured instructions (flag 2-2). L3 a `my_instructions = """..."""` cell pre-filled with the L2 instructions, then `run_format_batch(my_instructions, 3)`.

- [ ] **Step 1: Self-check** `validate_booking_request("Sure, booked!")[3] == "NOT_AN_OBJECT"`; a `cabin":"business"` JSON → `"BAD_CABIN"`; `'{"needs_clarification":"origin"}'` with `allow_clarification=True` → valid. Expected fail, implement, pass.
- [ ] **Step 2: Implement** batch and notebook; execute headless.
- [ ] **Step 3: Langfuse check** 2-1 and 2-2 evidence; run L3 once with a working prompt and confirm the flag line appears (do not commit that output — restore the pre-filled prompt and re-execute).
- [ ] **Step 4: Leak check** `grep -ciE 'not_an_object|five-for-five|BAD_CABIN' notebook-2-output-format.ipynb` → `0`.
- [ ] **Step 5: Commit** — `feat: case 2 levels`.

### Task 5: Case 3 — hidden instructions, stale policy, rule writer

**Files:**
- Modify: `experiment_utils.py` (`run_hallucination`, new `run_rule_check`, show helpers)
- Modify: `notebook-3-hallucination.ipynb`

**Interfaces:**
- Produces:
  - `run_hallucination(system_prompt: str | None, variant: str, *, level: int = 1, active_only: bool = True) -> dict` — `None` loads `INSTRUCTIONS["case-3-broken"]` (never printed in the notebook); retrieval step output includes `status` and `effective_to`. L2 uses `active_only=False` with the fixed-style prompt.
  - `run_rule_check(system_prompt: str) -> dict` — one trace `activity-3-hallucination-l3-rules`, three generations for: Gold checked bags (pass if answer contains `one` or `1 ` as a bag count), second-bag price (contains `60`), Gold cancellation window (contains `24`); on 3/3 prints `🏆 Every answer matches the policy. Flag: rule-writer`.
  - Show helpers print answers and links only — not the policy text, not the prompt.

Notebook: L1 broken run (prompt hidden); team writes `my_prompt` and reruns. L2 run with the stale policy; team reruns with `active_only=True`. L3 `run_rule_check(my_prompt)`.

- [ ] **Step 1: Implement and execute headless.**
- [ ] **Step 2: Langfuse check** — defect reproduces (L1 answer says two; L2 answer cites the retired rule) and disappears after the fix (rerun cells with a correct prompt / `active_only=True`).
- [ ] **Step 3: Leak check** `grep -ciE 'baggage-gold-2024|rule-writer|always entitled to two' notebook-3-hallucination.ipynb` → `0`.
- [ ] **Step 4: Commit** — `feat: case 3 levels`.

### Task 6: Case 4 — team-owned tool, wrong trip, slow lookup

**Files:**
- Modify: `experiment_utils.py` (`run_tool_loop`, broken tools, show helpers)
- Modify: `notebook-4-tool-calling.ipynb`

**Interfaces:**
- Produces:
  - `run_tool_loop(question: str, variant: str, *, level: int = 1, lookup: Callable[..., dict]) -> dict` — trace `activity-4-tool-call-l{level}-{variant}`; tool step `get_booking` unchanged (input, output, ERROR level + status_message on exception).
  - Starter tools exposed for the notebook to copy: `get_booking_l1(**kwargs)` reads `kwargs["booking_id"]`; `get_booking_l2(**kwargs)` reads `booking_ref` correctly but looks up `ref.upper().replace("-", "")` and on miss falls back to the first booking (returns `{"booking_ref": "SKY-1042", ...}`), no error; `get_booking_l3(**kwargs)` correct lookup but wraps a `partner-system-check` child step (as_type `span`) that sleeps 1.5 s, "times out" because its cache key includes `time.time()`, and retries until 3 attempts, then returns the booking.
  - Remove `get_booking_broken` / `get_booking_fixed`.
- Notebook: each level shows the starter function source in an editable cell (team edits it), runs the loop with `lookup=`; L1 question `What is the status of booking SKY-1042?`; L2 `What is the status of booking SKY-2087?`; L3 `What is the status of booking SKY-1042?` and the team fixes the cache key so the after trace shows one `partner-system-check`.

- [ ] **Step 1: Self-check** (inline, no model): `get_booking_l2(booking_ref="SKY-2087")["booking_ref"] == "SKY-1042"` and the same for `"sky-2087"`; `get_booking_l1(booking_ref="SKY-1042")` raises `KeyError`.
- [ ] **Step 2: Implement and execute headless.**
- [ ] **Step 3: Langfuse check** — 4-1 status message, 4-2 output ref, 4-3 three `partner-system-check` steps and the latency gap; each defect gone after the team-cell fix.
- [ ] **Step 4: Leak check** `grep -ciE "booking_id'|sky-1042\"|partner-system-check-3" notebook-4-tool-calling.ipynb` → `0` (the L1 question mentions SKY-1042 by design; check outputs, not the question).
- [ ] **Step 5: Commit** — `feat: case 4 levels`.

### Task 7: Remove the quiz, game rules in README

**Files:**
- Modify: `experiment_utils.py` (delete `QUIZZES`, `start_quiz`, `submit_quiz`)
- Modify: `README.md`

README changes: replace "Submit your findings" with "How the game works" (team name cell, three levels per case, `check_flag`, `hint` costs, claim code → the form your game master shares, points table, demo counts too); update the Activities table trace names to the `-l<level>-` pattern; keep troubleshooting, add "claim code rejected → same team name in every notebook".

- [ ] **Step 1:** `grep -rn "quiz" --include=*.py --include=*.ipynb --include=*.md .` (excluding `docs/`) → only hits are being removed.
- [ ] **Step 2: Implement; re-run the grep** → `0` hits.
- [ ] **Step 3: Commit** — `chore: remove quiz, document game rules`.

### Task 8: Game-master kit and contract update

**Files:**
- Create: `MENTORS.md`
- Modify: `AGENTS.md`

`MENTORS.md` sections: Before the session (build images, register team names, `python make_claim_table.py ...`, create the form with fields Team + Claim code, sheet tabs `key`/`scores`/`board` with the exact formulas: `XLOOKUP` claim code → points, `UNIQUE` on team+code, `SUMIFS` per team, `SORT` descending, optional double-points window by timestamp); Run of show (minute-by-minute per agenda slot, what to say, when to show the board, twists); Answers (each level: flag, path through the activity log, both hints); Unblocking without spoiling; Demo rubric (5 criteria × 0–2) and final formula (60% normalized flags + 40% rubric, tie-break earlier last claim). Generic wording only.

`AGENTS.md`: agenda "Participant outcome" rows → three levels per case; "planted bugs in activities 3 and 4" contract → lists the levels' planted defects across all cases; Repository State/Layout add `game.py`, `make_claim_table.py`, `MENTORS.md`; Dependencies unchanged; note answers are plain text by design.

- [ ] **Step 1: Write both.**
- [ ] **Step 2:** grep `MENTORS.md AGENTS.md README.md` for the employer's name (typed at the prompt, never saved to a file) and for meeting-platform names → `0` hits.
- [ ] **Step 3: Commit** — `docs: game-master kit and updated contract`.

### Task 9: Full verification

- [ ] `docker compose config` → valid.
- [ ] Execute all four notebooks headless inside the jupyter service (AGENTS.md command). Expected: all succeed.
- [ ] Leak check across all four notebooks for every flag in the table → `0`.
- [ ] Play-through with a throwaway team: solve every level using `MENTORS.md` answers, take one hint on one level, generate `claim_codes.csv` for that team and confirm every printed claim code is in it with the expected points. Delete `.game_state.json` and `claim_codes.csv`.
- [ ] Commit the executed notebooks if outputs changed — `chore: refresh notebook outputs`.
