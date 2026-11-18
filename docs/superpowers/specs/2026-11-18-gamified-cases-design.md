# Skyline Travel: Incident Shift — game design

Game-master design. Contains answers. This repository is a reusable template: answers are committed in plain text on purpose, and an internal copy is made later. No employer, event, date or meeting-platform names anywhere.

## 1. Intent

The four existing activities are well structured but too short and they give away the answer: the case notes name the bug and the fix is pre-written. Participants are smart colleagues. Turn the same four activities into a game that rewards investigating activity logs (Langfuse traces), with escalating difficulty, so fast teams stay busy and slow teams still finish Level 1 in every case.

Success looks like: every team closes Level 1 of all four cases; the strongest teams reach Level 3; the scoreboard changes leaders during the session; demos show before/after traces, not slides of prose.

## 2. Goals, non-goals, anti-goals

Goals
- Three levels per case, same theme, each harder (Gandalf pattern).
- Points only for evidence found in the activity log: a flag (CTF pattern).
- Self-service hints that cost points (CTFd pattern).
- A game master who narrates and unblocks, never bookkeeps.
- Plain business language kept in all participant text.

Non-goals
- No new service in the compose stack, no shared/central Langfuse, no CTF platform.
- No changes to agenda timings or activity numbering/order.

Anti-goals (failure even if it "works")
- A flag that can be found by reading notebook text or `experiment_utils.py` instead of the trace.
- A flag whose value depends on which model a team uses (teams bring their own `OPENAI_MODEL`).
- Any mention of an employer, a real event, a date, or a meeting platform in the repository.
- Level 1 so hard a team leaves a case with zero points.

## 3. Constraints

- Every team runs its own `docker compose` stack on localhost, remote included. Nothing is shared between teams.
- Facilitation is remote, single game master.
- Agenda fixed: Case 1 35 min, Case 2 20 min, Case 3 20 min, Case 4 40 min, demos 30 min.
- Repository rules (AGENTS.md): business language, reusable logic in `experiment_utils.py`, planted defects visible in the trace and not explained in comments, traces named by activity, one session per run, flush at the end, changes split into pieces of at most 3 files.
- **Flag determinism rule:** a flag is always derived from code-controlled data (document ids, retrieval filters, tool arguments, error messages, span names, counts the code controls), never from the model's wording or token counts. Goal-based "achievement" flags (Levels where the team must make something pass) are emitted by the harness when a code-side check passes.

## 4. Approaches considered

| | Approach | Trade-off | Decision |
|---|---|---|---|
| A | Flags + game master keeps a spreadsheet by hand | Least code; but a solo game master cannot type scores and give hints while narrating | Rejected (solo) |
| B | One shared Langfuse on the game master's laptop, scores written automatically | Fully automatic; but one machine and one network become a single point of failure, and remote teams cannot run independently | Rejected (each team must run independently) |
| C | CTF platform (CTFd) next to the stack | Real leaderboard and hint shop; adds a service the repo forbids and a lot of setup in 8 days | Rejected |
| **D** | **Flags verified locally; the notebook prints a claim code that already encodes hint usage; teams paste claim codes into an online form; the form's spreadsheet scores itself and is screen-shared** | No shared infrastructure, failures stay with one team, hints need no honesty; cost: a team can see the claim codes only after finding the flag, and a determined reader of the source could forge a "no hint" code | **Chosen** |

## 5. Game mechanics

### Team identity
First code cell of every notebook: `TEAM = "..."` (participant edits). The team name goes into Langfuse tags and into the claim code, so codes cannot be swapped between teams.

### Flags
- `check_flag("1-2", "baggage-gold")` → compares a normalized guess (lowercase, trimmed) against a salted SHA-256 stored in `experiment_utils.py`. No plaintext flags in the repository.
- Correct → prints `✅ Level 1-2 solved. Claim code: 1-2-7KQF` and a one-line story beat. Wrong → `❌ Not quite. Hints available: hint("1-2")`. Unlimited attempts; no penalty for wrong guesses (keeps it playful).

### Hints
- `hint("1-2")` shows the next hint for that level (max 2 per level) and records it in a local state file next to the notebooks (`.game_state.json`, gitignored).
- Hint 1 costs 25% of the level's value, hint 2 another 25%.

### Claim codes
- Code = level + 4 characters from `sha256(salt + TEAM + level + flag + hints_used)`.
- The game master's private kit generates the lookup table for every team name × level × hints-used (0/1/2) → points. The spreadsheet scores each form row by lookup; an unknown code scores 0 and is highlighted.
- Known weakness, accepted: a team can delete the state file to hide hints, or read the source to forge a code once they know the flag. Colleagues, not adversaries.

### Points

| Level | Value | With 1 hint | With 2 hints |
|---|---|---|---|
| L1 | 100 | 75 | 50 |
| L2 | 200 | 150 | 100 |
| L3 | 300 | 225 | 150 |

Maximum 600 per case, 2400 across the four cases, plus one hidden bonus flag (§6.5) worth 150 → 2550.

No first-to-solve point bonus (casual-group advice). The game master calls out first solves in the meeting chat instead.

### Scoreboard
An online form (Team, Claim code). The linked spreadsheet has a hidden `key` tab (the generated lookup), a `scores` tab (sum per team, de-duplicated by code) and a `board` tab sorted descending, which the game master screen-shares between cases.

### Winner
Final = 60% flag points (normalized to the top team) + 40% demo rubric. Tie-break: the team whose last claim was earlier.

Demo rubric — each 0/1/2, 10 points total, scored by the game master during the 30-minute slot (≈3 min per team):
1. Evidence: shows real activity-log links, not screenshots of answers.
2. Root cause: names the cause in one sentence a business colleague understands.
3. Proof: a before/after pair of activity logs for one fix.
4. Cost or speed insight: one number from the logs (tokens, cost, latency) and what drove it.
5. Story: would a non-technical stakeholder trust the assistant more after this?

### Game-master twists (optional, in the private runbook)
- "Breaking news" at the mid-point check: double points on Case 3 Level 3 for the next 10 minutes (the spreadsheet applies it by form timestamp).
- Bonus flag hint broadcast at the final break if nobody has found it.

## 6. Case designs

Common change to all four notebooks: delete the quiz cells; remove sentences in case notes that name the bug or the fix; each level ends in a `check_flag` cell; the existing activity-log naming (`activity-<n>-...`) and sessions stay, with a level suffix (`activity-1-rag-l2-...`).

### 6.1 Case 1 — Searching the right policy (35 min)

The corpus grows from 8 to ~20 policies so retrieval has real competition (more fares × topics, plus decoys).

- **L1 — The wrong fare.** Existing comparison without/with fare filter. *Find:* the id of the policy the unfiltered search wrongly used. *Flag:* `baggage-gold`.
- **L2 — Two questions, one answer.** A Silver customer asks about a cabin pet and the price of a second bag. Search returns only the single best policy, so half the question is answered from nothing. The team reruns with `run_rag(..., top_k=...)` and/or `topic=...` (new parameters). *Find:* the id of the policy the first run never retrieved. *Flag:* the second-bag policy id.
- **L3 — Playing it safe gets expensive.** A third variant "sends every policy to be safe". The answer is fine; the cost is not. *Find in the trace:* how many policies were sent in the prompt. *Flag:* the corpus size (code-controlled). The team also reports the token difference in their demo.

### 6.2 Case 2 — Getting a usable answer (20 min)

- **L1 — The prose problem.** Existing free text vs structured. The validator now writes a reason code into the trace (`NOT_AN_OBJECT`, `MISSING_FIELD`, `BAD_DATE`, `BAD_CABIN`, ...). *Flag:* the reason code of the free-text run.
- **L2 — Five messy requests.** A batch of five real-sounding requests: relative date ("next Friday"), "me and my partner", "business class", a missing destination, a clean one. Each runs as its own step in one activity log. *Find:* the field the booking contract cannot represent for request 3. *Flag:* `cabin`.
- **L3 — Make the next system happy.** The team edits the instructions in a notebook cell (a `my_instructions` string). The harness accepts either a valid booking or a valid `needs_clarification` object naming the missing field. When all five pass, the harness prints the achievement flag. Model-independent because the condition is checked by code.

### 6.3 Case 3 — Correcting a wrong answer (20 min)

The broken instructions are no longer shown in the notebook: they are loaded from a data file and only visible in the generation's system prompt in the activity log.

- **L1 — The generous promise.** Existing contradiction (instructions promise more bags than the policy). *Flag:* the number the instructions promise: `two`.
- **L2 — Faithful to the wrong page.** Retrieval returns a retired 2024 policy (effective dates visible in the retrieval step's output). The model faithfully quotes outdated rules — the "hallucination" is in the data, not the model. *Find:* the id of the outdated policy. *Flag:* that id. Fix: use the `active_only=True` retrieval option.
- **L3 — Write the rule.** The team writes their own instructions. The harness asks three questions with known answers (bags, second-bag price, cancellation window) and checks the numbers by code. All three correct → achievement flag.

### 6.4 Case 4 — Fixing a failed lookup (40 min)

The tool implementation moves into a notebook cell the team owns and passes in: `run_tool_loop(question, lookup=my_get_booking)`. The broken version is what they start with; there is no pre-written fix.

- **L1 — The wrong label.** Existing key mismatch. *Flag:* the key the tool tried to read: `booking_id`.
- **L2 — The wrong trip.** After the L1 fix, a customer writes the reference in lowercase. The tool falls back to "the first booking" when the lookup misses and returns a different customer's trip — no error, wrong answer. *Find in the tool step:* which reference was actually returned. *Flag:* that reference. Fix: normalize the reference, return a clear "not found" instead of a fallback.
- **L3 — The slow lookup.** A variant of the tool "checks the partner system" with an automatic retry on timeout; a bug in its cache key means it never hits the cache, so every call waits and retries. *Find:* the name of the step that takes the most time, and how many times it ran. *Flag:* `<step-name>-<count>` (both code-controlled). Fix: correct the cache key; the after trace shows one call.

### 6.5 Hidden bonus flag

One code-controlled value placed in a span's metadata in Case 1 that no instruction mentions, labeled like a detective's note. Worth 150. Rewards teams who explore every field of a trace. Hint broadcast by the game master at the last break if unclaimed.

## 7. What gets built (repository)

All participant text in plain business language. No event, company, date or platform names.

1. Remove the quiz: `experiment_utils.py` (QUIZZES, start_quiz, submit_quiz) + quiz cells in the four notebooks.
2. Game helpers in `experiment_utils.py`: `TEAM` handling, `check_flag`, `hint`, claim codes, state file; `.gitignore` entry for `.game_state.json`.
3. Corpus and fixtures in `data/`: expanded policies (with tier, topic, effective dates, status), extra bookings, five messy requests, Case 3 broken instructions file.
4. Activity helpers per case (new parameters and variants: `top_k`, `topic`, `send_all`, reason codes, batch run, `active_only`, `lookup=` injection, slow-tool variant).
5. One notebook per case rewritten to three levels (Case 1, 2, 3, 4 as separate pieces).
6. `README.md`: game rules (team name, flags, hints, claim codes, scoring), no form link. `MENTORS.md`: the whole game-master kit (see §8).
7. `AGENTS.md`: update the agenda/participant-outcome rows and the "planted defects" contract to the new levels; note the game-master kit and its plain-text answers live in `MENTORS.md` and `make_claim_table.py`.

Verification per piece: fresh-kernel execution of the touched notebook against a local stack; each level's trace shows the evidence its flag needs; Cases 3 and 4 defects reproduce before and disappear after the fix. Committed notebooks ship executed with Level-1 outputs and with `check_flag` cells left on a placeholder guess so outputs do not reveal flags.

## 8. Game-master kit (`MENTORS.md` + `make_claim_table.py`)

Answers are plain text by choice (template repository; honor system on the day). This design stays in `docs/superpowers/specs/`.

- Answers: every flag, the reasoning path through the trace, both hints.
- `make_claim_table.py` (repository root, the only script): takes the team-name list and writes `claim_codes.csv` for the spreadsheet's `key` tab.
- Scoreboard setup: how to build the form and spreadsheet formulas (lookup, de-dup, timestamp-based double points).
- Runbook: minute-by-minute script for the session, twist timings, demo rubric sheet.

## 9. Left to the builder

- Exact salt and code format, hint wording, the ~20 policy texts, the five request texts, span and step names for the slow tool.
- How to stop committed outputs from leaking flags (e.g. no printing of the flag-bearing field in notebook output; teams must open the trace).

## 10. Calls I made (check these)

- Level values 100/200/300 and hint cost 25% each.
- Wrong guesses are free.
- 60/40 split between flags and demo; tie-break by earlier last claim.
- Teams enter their name in the notebook; you pre-register team names before the session so claim codes can be generated.
- Expanded corpus to ~20 policies.
- Hidden bonus flag in Case 1.
- All game-master text lives in one `MENTORS.md` (per AGENTS.md); one script, `make_claim_table.py`, at the root. No new folders.
