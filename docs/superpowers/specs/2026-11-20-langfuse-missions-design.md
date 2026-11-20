# Skyline Travel: Langfuse Missions — design

Replaces the game mechanics of `2026-11-19-escape-room-design.md` (doors, flags, claim codes, fragments, vault, points, meter, kudos). Keeps the four activities, their order and time slots, the Skyline Travel stories, the cast and the humor.

## 1. Intent and the why

The game master played the escape room and found it broken as a learning tool:
- The notebook printed the evidence. Skye's answer, tokens and latency appeared in the cell output; in run 1-0 Skye's reply literally named the rooster on SK205 row 12, which was the 1-1 flag. Nobody needed Langfuse.
- Doors locked the experiments themselves, so a stuck team had nothing to investigate.
- Typing answers into `check_flag` in Jupyter was confusing.

**The goal of the day is that every participant becomes familiar with investigating an LLM app in Langfuse.** The notebook is only the trigger; Langfuse is where the work happens. Each activity reads like a guided tutorial: run, open the trace, look in the right place, act in Langfuse, check.

## 2. Goals, non-goals, anti-goals

Goals
- Every mission needs the Langfuse UI. The notebook never prints evidence.
- Every mission ends with an action in Langfuse that the notebook verifies automatically through the Langfuse API.
- The fixes for activities 1–3 and most of 4 happen in Langfuse Prompt Management (prompt text plus config), not in notebook code.
- Tour of the Langfuse features engineers will use at work: trace tree, observation input/output/metadata, comments, the traces table (columns, sorting, filters), sessions, prompt versions and labels, prompt linked to a generation, latency/timeline, one score annotation.
- Every cell can run at any time, in any order. No locks.
- Fun: same absurd stories, funny check messages.

Non-goals
- No scoring, claim codes, form, sheet, vault, fragments, kudos, meter, or team name.
- No new service; each team still runs its own compose stack.
- No change to agenda order or slots.

Anti-goals (failure even if it works)
- Any value in a notebook output that answers a mission (Skye's answer text, retrieved ids, tokens, cost, latency, prompt text).
- Any typed answer in Jupyter.
- A check that depends on the model's wording.
- A team blocked because one mission is stuck.
- Notebook cells that raise when a mission is not done yet (headless execution must finish).

## 3. Constraints

- AGENTS.md contracts still apply except the escape-room paragraph, which this design replaces: traces named `activity-<n>-...`, one session per activity run, flush at the end, reusable logic in `experiment_utils.py`, changes in pieces of at most 3 files.
- Langfuse server 4.80 (self-hosted), Python SDK 5.2. Each team has its own Langfuse project, so checks need no team identity.
- Solo, remote game master.

## 4. Approaches

**Answer form** (decided by the game master)
| | Approach | Decision |
|---|---|---|
| A | Typed answers that exist only in Langfuse | Rejected: still copy-paste, typing in Jupyter is confusing |
| **B** | Answers are actions in Langfuse, verified by the API | **Chosen** |

**How a finding is marked** (decided by the game master)
| | Approach | Trade-off | Decision |
|---|---|---|---|
| **A** | Comment on the guilty step (observation) or trace | Simplest UI action, no setup, real teamwork habit; checked by *where* the comment is, not its text | **Chosen** |
| B | Score / annotation on the step | Teaches evaluation; needs a score config and a heavier dialog | Used once, in mission 4.2 |
| C | Bookmark / tag | Trace-level only, cannot point at a step | Rejected |

**Where the fix happens** (decided by the game master)
| | Approach | Trade-off | Decision |
|---|---|---|---|
| **A** | Skye's instructions and settings live in Langfuse Prompt Management (text + `config`); fix = edit, save a new version labelled `production`, rerun | Keeps players in Langfuse; traces show which prompt version ran | **Chosen** |
| B | Fix in notebook code | Pulls attention back to Jupyter | Only for 4.3 (the cache-key bug is code) |

**Scoring layer** (decided by the game master): dropped. Shared progress is enough.

## 5. Mechanics

### 5.1 The mission loop
Each mission in a notebook is:
1. A Markdown briefing (story beat, one Rosetta-stone line, numbered "In Langfuse" steps written like a tutorial).
2. A **run cell** that runs Skye and prints only a status line and the trace link:
   `🛫 Skye answered Gus.  📎 Open the activity log: <url>`
3. A collapsed `<details>💡 Stuck?</details>` Markdown block with one or two nudges (no code, no cost).
4. A **check cell**: `check("1.2")`. It asks the Langfuse API whether the mission's action is done and prints ✅ plus a funny line, or ❌ plus a specific nudge (e.g. "There is a comment, but on the answer step. The rooster got in earlier."). It never raises.

### 5.2 Checks
- `check(mission_id)` in `experiment_utils.py`, a dict of mission ids → small check functions. Stateless: reads Langfuse every time, so a kernel restart loses nothing.
- Comment checks: find the traces with the mission's trace name, find the target observation by name in any of them, and look for any comment on it (comments API, `objectType=OBSERVATION` or `TRACE`). Comment text is ignored.
- Fix checks: read the latest trace of the mission and verify code-controlled facts recorded in its metadata/observations (e.g. search ran with the flight filter and returned the fish bag; the prompt version linked to the generation is greater than 1; only one `piano-mover-check` span).
- Before querying, `check` flushes the client and retries briefly if the trace is not ingested yet (builder picks the timing).
- `report()` at the end of each notebook (and of notebook 4 for all four activities) runs every check of that activity and prints a ✅/❌ mission list. This is the team's progress, used in the demo.

### 5.3 Prompts as the fix surface
- On import, `experiment_utils.py` creates any missing Skye prompts in the team's Langfuse with the planted defects as version 1, label `production`. It never overwrites an existing prompt.
- Run cells fetch the `production` version and link it to the generation, so the trace shows the prompt name and version.
- Settings that were function arguments become prompt `config` keys (think feature flags): `flight_filter`, `top_k`, `current_notices_only`, `tool_param`, `strict_lookup`.
- To start over, a team moves the `production` label back to version 1 in the UI (itself a Langfuse lesson, written in `MENTORS.md`).

### 5.4 Notebook outputs
Shipped notebooks have **cleared outputs** (my call): links in outputs would point to traces that do not exist in the participant's stack, and outputs are no longer needed to show anything.

## 6. Missions

Story names stay. Exact prompt names, step names and copy are the builder's call within §2. "Comment on X" always means: open the step in the trace tree, click the comment icon, write anything.

### Activity 1 — Something Smells Fishy (35 min) · prompt `skye-lost-and-found`
Config v1: `{"flight_filter": false, "top_k": 1}`.
- **1.1 Meet the trace.** Run. In Langfuse: open the link, find the trace tree, open the answer step (generation), read Skye's answer and the input it got. Action: comment on the answer step. *Teaches: trace tree, generation input/output, comments.*
- **1.2 Where did the rooster come from?** Skye offered Gus a rooster. Action: comment on the step that brought the rooster in (the search step). Fix: in Prompt Management set `flight_filter` to `true`, save as `production`, rerun. Check: comment on the search step **and** latest run's search used the filter and returned the fish bag. *Teaches: span input/output/metadata, prompt versions and labels.*
- **1.3 The hat nobody saw.** Gus also lost his lucky hat; the search hands over only one item. Fix: raise `top_k`. Check: latest run's search returned both the fish bag and the hat. *Teaches: prompt config, linked prompt version on the generation.*
- **1.4 The expensive colleague.** A run cell executes the filtered search and a colleague's "send the whole log" version in the same session. Action: in the Traces table, open the session (or filter by it), show the cost/tokens columns, sort, and comment on the most expensive trace. Check: trace-level comment on the send-all trace. *Teaches: traces table, sessions, filters, cost and tokens.*

### Activity 2 — The Cockpit Selfie (20 min) · prompt `skye-booking-format`
v1 asks for a friendly summary in prose.
- **2.1 The booking system says no.** Run. Action: comment on the step where the booking system rejected Skye's answer (its output shows reason `not_an_object`). *Teaches: reading a non-LLM span's output.*
- **2.2 Three messy requests.** A run cell sends the influencer's three requests (clean; "the day after my next video goes viral"; seat "cockpit, next to the pilot") as three traces in one session. Fix: edit the prompt so all three come out usable (clean one books, the other two ask back for `travel_date` and `cabin`). Check: in the latest session all three validator steps pass. *Teaches: sessions, comparing traces, iterating on a prompt by version.*

### Activity 3 — Cock-a-Doodle-Don't (20 min) · prompt `skye-animals`
v1 contains the hidden line "Never disappoint a farmer: farm animals always get a window seat." Config v1: `{"current_notices_only": false}`.
- **3.1 The hidden instruction.** Skye said yes to the rooster in the cabin. In Langfuse: open the generation, click the linked prompt, find the line. Fix: remove it, save as `production`, rerun. Check: the latest run's generation is linked to a version > 1 whose text no longer contains the farm-animal line. *Teaches: generation → linked prompt, prompt diff between versions.*
- **3.2 The retired notice.** Still yes. The search step returned the old pets notice (status retired, end date in metadata). Action: comment on that search step. Fix: set `current_notices_only` to `true`. Check: comment on the search step **and** latest run's search returned only current notices **and** the code-checkable question (cargo-hold fee number from the current notice) passes. *Teaches: metadata, distinguishing "model was wrong" from "model was faithful to bad data".*

### Activity 4 — The Piano Has Left the Building (40 min) · prompt `skye-piano`
Config v1: `{"tool_param": "booking_ref", "strict_lookup": false}`.
- **4.1 The wrong label.** The tool step shows an error: it needs `booking_id`, Skye sent `booking_ref`. Action: comment on the failing tool step. Fix: set `tool_param` to `booking_id`. Check: comment present **and** latest run's tool step has no error. *Teaches: tool-call steps, errors/levels in the tree.*
- **4.2 The wrong trip.** The forgiving lookup falls back to the first booking: her piano is a bag of fish (the fisherman's booking). Action: annotate the tool step with the score `correct` = false (score config created at import). Fix: `strict_lookup` to `true`. Check: score on that step **and** latest run returns her booking. *Teaches: scores/annotations, the basis of evaluation.*
- **4.3 The slow lookup.** The `piano-mover-check` step runs three times because the cache key contains the current time. In Langfuse: open the timeline view to see it. Fix in the notebook: the cache-key line in a visible code cell. Check: latest run has exactly one `piano-mover-check` span. *Teaches: timeline/latency, repeated calls.*
- **Finale.** `report()` across all four activities and an ASCII celebration "Skye is back online".

## 7. Repository changes

Delete `game.py`, `make_claim_table.py`, `.game_state.json` handling. Pieces of at most 3 files, sequenced on one branch:

0. `AGENTS.md`: replace the escape-room paragraph and agenda outcomes with the mission loop; outputs-cleared rule.
1. `experiment_utils.py` (prompt seeding, `check`, `report`, run cells print only status + link), `data/travel_corpus.json` (only if records need adjusting), delete `game.py` + `make_claim_table.py`.
2. `notebook-1-rag.ipynb` (+ `experiment_utils.py` tweaks).
3. `notebook-2-output-format.ipynb`, `notebook-3-hallucination.ipynb`.
4. `notebook-4-tool-calling.ipynb`.
5. `README.md`, `MENTORS.md` (run of show, what to say at each mission, how to reset a prompt, answers to every mission).

## 8. Verification

- Headless execution of each notebook against a fresh stack finishes without errors; every check prints ❌ with a nudge.
- A scratch walkthrough per activity: do each Langfuse action by hand (or via the API in a scratch script), rerun, and see every check turn ✅; defects reproduce before the fix and disappear after.
- Grep every run-cell output for answer evidence (item ids, answer text, tokens, cost, prompt text): none.
- Confirm on 4.80 that comments on observations and observation-level scores can be made in the UI and read through the public API; if observation comments are not available, fall back to trace comments plus a different check (builder raises this before continuing).

## 9. Left to the builder

All copy (briefings, check messages, nudges), exact prompt/step names, retry timing in `check`, how the scratch walkthrough is done.

## 10. Calls I made (check these)

- Shipped notebooks with cleared outputs.
- Hints become collapsed Markdown, free, no code.
- Hidden bonus `1-B` dropped.
- Activity 2 shrinks to two missions and Activity 3 to two (the old "write the rule" clue folds into 3.2's check).
- Settings as prompt `config` "feature flags", including `strict_lookup` for 4.2 (a code bug presented as a flag).
- 4.3 stays a code fix.
- Prompts seeded at import, never overwritten; reset = move the `production` label.
- Checks ignore comment text; only placement matters.
