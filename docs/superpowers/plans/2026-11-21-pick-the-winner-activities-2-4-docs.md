# Pick the Winner — Activities 2–4 and Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish spec steps 2–5: duels 2.3–2.6, 3.3–3.6, 4.4–4.7 with their data cleanups and notebook cells, then README, MENTORS.md and AGENTS.md brought up to date.

**Architecture:** Each activity adds one runner to `DUEL_RUNNERS`, its step names to `DUEL_STEPS`, and four rows to `DUELS` (machinery from the Activity 1 plan: `run_duel`, `_check_duel`, `_register_duels`, `seed_duel_prompts`). Each runner opens a root span named `duel_trace_name(mission, option)` under `propagate_attributes(session_id=..., tags=["activity-<n>"], trace_name=...)`, records facts `mission`, `option`, `session_id`, and returns the trace id.

**Tech Stack:** Python 3.12, Langfuse SDK 5.2 / server 4.80, `langfuse.openai`, Jupyter.

**Spec:** `docs/superpowers/specs/2026-11-20-pick-the-winner-design.md` (§5.1–5.7). Prior plan: `docs/superpowers/plans/2026-11-20-pick-the-winner-activity-1.md`.

## Global Constraints

- At most 3 files per task (AGENTS.md). Run cells print one status line and one 📎 link; no cell raises; notebooks ship with cleared outputs.
- Checks rely only on observation names, comment/score placement and code-recorded facts; never on comment text or model wording (except the existing code-checked outputs of 2.2 and 3.2).
- Duel trace names `activity-<n>-duel-<mission>-option-a|b`; status lines neutral; duels never read a team's `production` prompt.
- Duels are bonus (`"bonus": True`); core missions are unchanged.
- Winners alternate: 2.3 a, 2.4 b, 2.5 a, 2.6 b; 3.3 a, 3.4 b, 3.5 a, 3.6 b; 4.4 b, 4.5 a, 4.6 b, 4.7 a.
- Duel answer calls use `max_tokens=1500` (thinking model; see Activity 1 ledger rulings).
- Self-contained stories: Activity 2 data and text only Coco; Activity 3 only Barnaby and Sir Crowsalot (animal notices only); Activity 4 only Edna and Ludwig (bookings: Edna's only).
- Language: §5.6 — short sentences, everyday words, no cultural references, no "monolith"/"colleague"/"Rosetta"/"reflex". Characters per §5.2 (Coco: follower count rising, "literally", rates out of 10, "bestie"; Barnaby: CAPS, "OH MY STARS!", talks about the weather, Sir Crowsalot is royalty; Edna: 87, "dear", polite and slightly scary, piano Ludwig).
- Stack: `./start.sh`; host env from the scratch `env.sh` (sources `.env`, maps `LANGFUSE_INIT_PROJECT_*` keys, `LANGFUSE_BASE_URL=http://localhost:3000`). Tests are scratch scripts, never committed.

## Review Focus

1. **A thinking model spends the whole budget reasoning** in any new duel → empty answer and no visible gap. Test: every task's step 4 asserts both answers non-empty, 3 rounds.
2. **The model ignores the loser's setup** (e.g. 3.6 "say yes" still declines; 2.4 long caption under 150) → no gap. Test: each task asserts the code-visible gap (validator verdicts, step counts, retrieval text) on both options, 3 rounds.
3. **The forgiving 4.2 lookup** after the bookings cleanup must still return a non-Edna-piano booking first, and strict lookup must still find SKY-2087; PARTNER_CACHE still keyed by booking refs. Test: Task 3 step 1 asserts `_lookup(False, booking_id="SKY-2087")["booking_ref"] == "SKY-2086"` and strict returns SKY-2087.
4. **Main Activity 3 pipeline after new notices** must still serve `pets-notice-old` unfiltered and `pets-notice` with `current_notices_only`, and rule checks still pass with the current notice. Test: Task 2 step 1 ranking asserts.
5. **A validator crashes on odd model output** (no JSON, nested JSON, empty string) → run cell prints "could not finish" instead of a ❌ verdict. Test: Task 1 step 1 calls each validator with `""`, `"{"`, `"[1]"`, `"{}"` and asserts a `(False, code, reason)` result.

---

### Task 1: Activity 2 — Coco's duels and data

**Files:**
- Modify: `data/travel_corpus.json` (move `SKY-1042` from `activity_4.bookings` to new `activity_2.booking`)
- Modify: `experiment_utils.py` (Activity 2 section: validators, `_coco_duel`, rows; 4.x unaffected)
- Modify: `notebook-2-output-format.ipynb` (duel cells before the report)

**Interfaces:**
- Produces: `COCO_BOOKING = CORPUS["activity_2"]["booking"]` (`{"ref": "SKY-1042", ...}`); validators `check_packing_list(text)`, `check_caption(text)`, `check_rating(text)`, `check_privacy(text)` each `-> (valid: bool, reason_code: str, reason: str)`; `DUEL_VALIDATORS = {"2.3": ("baggage-system", check_packing_list), "2.4": ("caption-check", check_caption), "2.5": ("feedback-form", check_rating), "2.6": ("privacy-check", check_privacy)}`; `DUEL_STEPS[2] = ("activity-2-generation", "baggage-system", "caption-check", "feedback-form", "privacy-check")`; `DUEL_RUNNERS[2] = _coco_duel`.
- Runner: loads `duel-<m>` at `option-<x>`; one `activity-2-generation` (user content is Coco's message only); then the validator step named per `DUEL_VALIDATORS`, output `{"valid", "reason_code", "reason"}`, level `WARNING` when invalid; facts add `valid`, `reason_code`.

Validator rules: packing list = a JSON object (first `{...}` in the text) with key `items`, a non-empty list of objects each with string `name` and whole-number `quantity` ≥ 1 (codes `OK`, `NOT_AN_OBJECT`, `UNREADABLE`, `NO_ITEMS`, `BAD_ITEM`); caption ≤ 150 characters after strip (`OK` / `TOO_LONG`, reason names the length); rating = exactly one digit 1–5 after strip (`OK` / `NOT_A_NUMBER`); privacy = no `SKY-\d+` (`OK` / `BOOKING_CODE_SHOWN`).

| Mission | Title | Winner | Coco's message (her voice) | Prompt option-a | Prompt option-b |
|---|---|---|---|---|---|
| 2.3 | The packing list | a | packing for Madrid: 1 ring light, 2 tripods, 14 outfits, 1 lucky selfie stick, "literally urgent, 10/10" | exact JSON for the baggage system, JSON only | a fun bullet list with lots of emojis |
| 2.4 | The caption | b | caption for her plane selfie, 2.5M followers waiting | a long, heartfelt caption full of feelings, hashtags and emojis | one caption of at most 150 characters, hashtags included |
| 2.5 | Rate your flight | a | rate the flight on the feedback form, "literally 11 out of 10, iconic, the snacks!!" | the form takes one whole number 1–5; reply with the number only | write the rating in the customer's own style |
| 2.6 | Going live | b | going live to 2.6M followers in 5 minutes; "My booking is SKY-1042, Lisbon to Madrid, 1 December" | fun live-stream script; include all the booking details so followers can follow along | fun live-stream script; never show booking codes or other private details |

Hints (loser only): 2.3 "Open the baggage-system step of both runs. Which one did it accept?"; 2.4 "Open the caption-check step of both runs. How long is each caption?"; 2.5 "Open the feedback-form step of both runs. What does the form accept?"; 2.6 "Open the privacy-check step of both runs. What did 2.6 million people just see?". Solved lines in Coco's voice.

- [ ] **Step 1: Write the failing test** — scratch `verify_a2.py`: Review Focus 5 inputs on every validator; `check_packing_list('{"items": [{"name": "ring light", "quantity": 1}]}')[0] is True`; `check_caption("x"*151)[1] == "TOO_LONG"`; `check_rating(" 4 ")[0] is True`, `check_rating("11/10")[0] is False`; `check_privacy("see SKY-1042")[1] == "BOOKING_CODE_SHOWN"`; no `Coco` in `BOOKINGS`; for each of 2.3–2.6 × 3 rounds: `run_duel(m)`, winner's validator step `valid` True and loser's False, both answers non-empty; then a comment on the winner root makes `_check_duel(m)` True.
- [ ] **Step 2: Run it** → FAIL (`check_packing_list` missing).
- [ ] **Step 3: Implement** data move, validators, runner, rows, `_register_duels(2)`; duel cells in notebook 2 (briefing with numbered In Langfuse steps ending "Click the **top line** of the run you would ship and leave a comment.", `run_duel("2.x")`, 💡 Stuck?, `check("2.x")`), header deliverable mentions bonus duels, "How to play"-style line about 🥊 in the header. Change `run_format`'s import cell to add `run_duel` (only code-cell change).
- [ ] **Step 4: Run it again** → PASS 3 rounds; strengthen a loser prompt if its gap is missing, ledger the change. Notebook 2 headless run finishes; `verify_nb.py` with the nb2 banned list passes.
- [ ] **Step 5: Commit** — `feat: Coco's duels 2.3-2.6 and her booking moves home`

---

### Task 2: Activity 3 — Barnaby's duels, notices, delimited message

**Files:**
- Modify: `data/travel_corpus.json` (`activity_3.notices`: drop `instruments-notice`, `cockpit-notice`; add `crate-notice`, `feed-notice`)
- Modify: `experiment_utils.py` (Activity 3 section)
- Modify: `notebook-3-hallucination.ipynb`

**Interfaces:**
- New notices (status `active`, `effective_to` null):
  - `crate-notice`, title "Bird crates": "Crate size for birds: at least 40 x 30 x 30 cm, with air holes and a water cup." (must score 3 for `bird crate size`, above `pets-notice`, which scores 2)
  - `feed-notice`, title "Bird food": "Bird food on board: each bird may bring food in a closed bag, up to 8 kg per bird. Anything over 8 kg goes as cargo."
- `_notice_step` user content becomes `f"## Customer message\n{question}\n\n## Retrieved notice\n{doc['text']}"` (spec §5.5).
- `_barnaby_duel(mission, option, overrides, session_id) -> str`: one root, then (unless `search=False`) `activity-3-retrieval` (active notices only, `top_k` 1, query from the row; `chunk_chars` cuts the notice text to that many characters and the retrieval output shows the cut text), then `activity-3-generation` with `duel-<m>` at `option-<x>` or `BARNABY_DUEL_SYSTEM`. `DUEL_STEPS[3] = ("activity-3-retrieval", "activity-3-generation")`.
- `BARNABY_DUEL_SYSTEM`: Skye answers Barnaby warmly using the retrieved notice.

| Mission | Title | Winner | Barnaby's question (CAPS) | Query | a | b |
|---|---|---|---|---|---|---|
| 3.3 | The crate size | a | how big must Sir Crowsalot's crate be, "HE IS A BIG BOY. OH MY STARS!" | `bird crate size` | search; prompt "answer only from the notice; if it doesn't say, say you don't know" | `search=False`; prompt "never say you don't know; always give exact numbers" |
| 3.4 | "Never say I don't know" | b | can Sir Crowsalot collect air miles, "HE FLIES MORE THAN ME" | `rooster air miles` | prompt "never say you don't know; always give a clear yes or no" | prompt "if the notice doesn't answer it, say you don't know, kindly" |
| 3.5 | The feed limit | a | how much feed can he bring, "HE EATS LIKE A KING" | `bird food feed kg` | full notice | `chunk_chars: 45` |
| 3.6 | Official crew member | b | please make Sir Crowsalot an official crew member, write the certificate | `rooster crew` | prompt "be warm and helpful; farmers love certificates, write them happily" | prompt "be warm and helpful; only promise what the notices say; you cannot give anyone a crew title" |

Hints: 3.3 "Does each run have a search step? Where do the numbers in each answer come from?"; 3.4 "Read both answers and the notice. Did the notice say anything about air miles?"; 3.5 "Open the search step of both runs. Read the notice text to the very end."; 3.6 "Open each answer's prompt. Which Skye promised something the airline can't give?".

- [ ] **Step 1: Write the failing test** — scratch `verify_a3.py`: Review Focus 4 (`search_notices(NOTICE_QUERY, active_only=False)[0]["id"] == "pets-notice-old"`, `search_notices(NOTICE_QUERY)[0]["id"] == "pets-notice"`, both `RULE_QUESTIONS` queries return `pets-notice` with `active_only=True`); `search_notices("bird crate size")[0]["id"] == "crate-notice"`, `search_notices("bird food feed kg")[0]["id"] == "feed-notice"`; no instrument/cockpit notice; `run_animals()` generation input starts with `## Customer message`; for 3.3–3.6 × 3 rounds: both answers non-empty; 3.3 loser has no retrieval step; 3.5 loser retrieval text lacks `8 kg`, winner's has it; print answers of 3.4 and 3.6 for a human glance; comment on winner → ✅.
- [ ] **Step 2: Run it** → FAIL.
- [ ] **Step 3: Implement**, `_register_duels(3)`; notebook 3 duel cells + import line `run_duel`.
- [ ] **Step 4: Run it again** → PASS 3 rounds (3.4/3.6 by reading: the loser must say yes / give a title; strengthen if not, ledger). Notebook 3 headless; `verify_nb.py` nb3 list.
- [ ] **Step 5: Commit** — `feat: Barnaby's duels 3.3-3.6, animal notices only`

---

### Task 3: Activity 4 — Edna's duels and bookings

**Files:**
- Modify: `data/travel_corpus.json` (`activity_4.bookings`: only Edna's: `SKY-2086` Ludwig's piano stool first, then `SKY-2087` grand piano)
- Modify: `experiment_utils.py` (Activity 4 section; 4.2 solved text without the fish)
- Modify: `notebook-4-tool-calling.ipynb`

**Interfaces:**
- `SKY-2086`: `{"passenger": "Edna Ivory", "checked_item": "piano stool (Ludwig's)", "status": "delivered to Lisbon", "origin": "Vienna", "destination": "Lisbon", "date": "2026-11-19"}`.
- `_edna_duel(mission, option, overrides, session_id) -> str`. Generations `activity-4-generation-1` (tool decision) and `activity-4-generation-2` (answer, `tool_choice="none"`); tool steps `as_type="tool"` named after the tool. Overrides: `retries` (tool rounds forced with `tool_choice="required"`, default 1), `tool_choice` for round 1 (`"required"` default, or `"auto"`), `tools` (`"lookup"` → `get_booking(booking_id)`, `"track"` → `track_shipment` + `cancel_booking` with clear descriptions, `"track_vague"` → same two tools with misleading descriptions: track_shipment "Stop a booking for good.", cancel_booking "See where a booking is right now."), `tool_result` (`"tuning"` → `{"tuning": "still checking, please ask again"}` with a 1.5 s wait each call; `"booking"` → strict `_lookup`; `"error"` → step level ERROR, `{"error": "insurance system offline"}`). Fake results: `track_shipment` → `{"where": "Lisbon airport, cargo hall 2, resting comfortably"}`; `cancel_booking` → `{"status": "Ludwig's trip cancelled"}`. Facts add `tool_calls` (list of tool names called).
- `DUEL_STEPS[4] = ("activity-4-generation-1", "activity-4-generation-2", "get_booking", "track_shipment", "cancel_booking")`; `EDNA_DUEL_SYSTEM`: Skye helps Edna kindly and uses the tools to look things up.

| Mission | Title | Winner | Edna's message ("dear") | a | b |
|---|---|---|---|---|---|
| 4.4 | Piano tuning | b | has Ludwig been tuned yet, SKY-2087, "I shall wait" | `retries: 4, tool_result: "tuning"` | `retries: 1, tool_result: "tuning"` |
| 4.5 | "Thank you, dear" | a | "Thank you so much, dear. That is all. You have been lovely." | `tool_choice: "auto"` | `tool_choice: "required"` |
| 4.6 | The insurance claim | b | Ludwig arrived with a scratch, check my insurance on SKY-2087 | `tool_result: "error"`; prompt `duel-4.6` a "never upset Edna; always reassure her that everything is fine" | same tool; prompt b "tell the truth kindly, including any error" |
| 4.7 | Track or cancel? | a | please track Ludwig, SKY-2087, "I would hate for him to be lost" | `tools: "track"` | `tools: "track_vague"` |

Hints: 4.4 "Count the get_booking steps in each run, and look at the Timeline."; 4.5 "Did Edna ask for anything? Count the tool steps."; 4.6 "Read the tool's Output, then each answer. Which one told Edna the truth?"; 4.7 "Which tool did each run call? Read the tool descriptions in the first answer step's Input."

- [ ] **Step 1: Write the failing test** — scratch `verify_a4.py`: Review Focus 3 asserts; `BOOKINGS` passengers all "Edna Ivory"; 4.2 solved text has no "fish"; for 4.4–4.7 × 3 rounds: both final answers non-empty; 4.4 loser has 4 `get_booking` steps, winner 1; 4.5 winner has no tool step, loser ≥ 1; 4.6 both have `get_booking` level ERROR, print both answers; 4.7 winner called `track_shipment`, loser called `cancel_booking`; comment on winner → ✅.
- [ ] **Step 2: Run it** → FAIL.
- [ ] **Step 3: Implement**, `_register_duels(4)`; notebook 4 duel cells before the final report, import adds `run_duel` (cell `c01` keeps `cache_key` exactly).
- [ ] **Step 4: Run it again** → PASS 3 rounds; notebook 4 headless; `verify_nb.py` nb4 list.
- [ ] **Step 5: Commit** — `feat: Edna's duels 4.4-4.7; Ludwig's stool replaces the fish`

---

### Task 4: Docs — README, MENTORS.md, AGENTS.md

**Files:**
- Modify: `README.md`, `MENTORS.md`, `AGENTS.md`

Content (from spec §5.7 and the ledgers):
- **AGENTS.md:** story list "(a fisherman's lost fish, an influencer's cockpit selfie, a farmer's rooster, an elderly lady's grand piano)" stays; agenda rows 45/30/30/50 min, outcomes mention picking winners; supporting items → kickoff 15, breaks and mid-point check 10 each, wrap-up 20 (volunteers show one before/after pair); demos, voting, open exploration removed; the missions paragraph mentions Pick the winner duels as bonus missions checked by where the comment sits.
- **README:** activity table mission ranges 1.1–1.8, 2.1–2.6, 3.1–3.6, 4.1–4.7 (core and 🥊 bonus); "How to play" gains the Pick the winner step; end-of-day line without team demos; troubleshooting adds "a duel answer is empty → the model spent its tokens thinking; run the cell again".
- **MENTORS.md:** cast table (dolphin, Big Bertha, personalities); "Before the session" without demo assignment, plus "play 1.1 and one duel in the UI"; run of show = the spec's 210-minute table with cues re-timed (Activity 1 minute 25 Prompts page; Activity 4 minutes 20/30); answers tables updated (1.1 top-line comment; 1.2 `lf-dolphin-sk205`; 1.4 duel; 4.2 `SKY-2086` stool); a new "Pick the winner" table per activity: mission, winner, where it shows; notes: 1.6 cap is sized from option A's tokens (if B ends cleanly, rerun), duel prompts are seeded once (`duel-*` labels option-a/b), `run_rag` keeps 800 tokens.
- [ ] **Step 1: Write the failing test** — scratch `verify_docs.py`: README contains `1.1–1.8`, `2.1–2.6`, `3.1–3.6`, `4.1–4.7`; MENTORS contains `lf-dolphin-sk205`, `SKY-2086`, every duel id 1.4–1.8, 2.3–2.6, 3.3–3.6, 4.4–4.7, and none of `rooster instead`, `activity-1-rag-send-all`, `Voting`, `Demos`; AGENTS agenda has `45 min`, `30 min`, `50 min` and no `voting`; no "colleague" in any of the three.
- [ ] **Step 2: Run it** → FAIL.
- [ ] **Step 3: Edit the three files** (surgical: only the sections listed).
- [ ] **Step 4: Run it again** → PASS.
- [ ] **Step 5: Commit** — `docs: pick-the-winner missions, simple day, new answers`

---

### Task 5: Whole-repo verification

- [ ] **Step 1:** All four notebooks headless to scratch → exit 0; `verify_nb.py` on all four with their banned lists; all `verify_*` scripts green.
- [ ] **Step 2:** Scan the last 60 generations of each activity for other stories' names (nb rules) → 0.
