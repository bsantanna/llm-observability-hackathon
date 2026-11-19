# Skyline Travel: Escape Room — game design

Replaces the game mechanics and the story content of `2026-11-18-gamified-cases-design.md`. The four observability lessons stay (search with and without a filter, output format, wrong answers from hidden instructions or stale data, a broken tool); the fare tiers, membership levels and policy puzzles go. Contains answers, in plain text by design. No employer, event, date, real person or meeting-platform names anywhere.

## 1. Intent and the why

The game master played Case 1 and found the levels-and-points game **too steep and a little boring**: every level has the same loop (run the cell, open the trace, copy a field, paste it), nothing depends on what you found, the content is dry airline policy (fares, memberships, rule checks), and the game opens with scoring rules before anything fun happens.

The players are the game master's colleagues: smart engineers from a non-LLM background who work together on a large monolith. They already debug with logs, call chains, stack traces and slow calls; LLM vocabulary is what is new.

The new game is an **escape room made of four comic Mini-Games**. Each Mini-Game is one absurd customer story; each clue's answer unlocks the next clue's briefing; each Mini-Game's last clue drops a fragment of a final vault code. Tone is **highly humorous, absurd and light**. The spirit is **collaborative**: the whole group gets the assistant ("Skye") back on its feet together and leaves with a shared understanding of the four failure modes. A scoreboard exists only to compute a final score.

Success looks like: every team escapes Mini-Game 1 within its slot; the group recovery meter keeps moving; teams help each other; the post-mortem shows every person heard every root cause once; people laugh.

## 2. Goals, non-goals, anti-goals

Goals
- Gentle on-ramp: an orientation clue that teaches "find the trace, open a step" before any LLM idea.
- Clues chain: a correct answer prints the next briefing and opens the next door; where natural, the answer is also the next run's input.
- Every clue is a story beat first, framed through a monolith instinct (wrong row from a query, missing argument, stale config, call that runs three times), then the LLM idea behind it.
- Humor everywhere participants read: briefings, lock messages, wrong-guess replies, solved messages, data records.
- Collaboration rewarded: a shared recovery meter, cheap hints, helper ("good colleague") points, fragments may be shared between teams.
- Scoreboard kept, demoted to the final tally.

Non-goals
- No new service, platform, or shared Langfuse. Each team still runs its own compose stack.
- No change to the agenda's activity order or time slots.
- No encryption or tamper-proof locks (approach B rejected; honor system as before).
- No fare tiers, membership levels, or policy-rule puzzles.

Anti-goals (failure even if it works)
- A team blocked for the rest of the session because one Mini-Game is stuck.
- A clue answer that depends on the model's wording or token counts.
- Humor that mocks a person, age, origin, a real group, a real person or a real company; any real employer, event, date or meeting platform in the repository.
- Notebook cells that raise when a door is locked (headless execution must still finish).
- Racing or ranking shown on screen during play.
- A "fix it" step that turns into a long rules exercise (the old five-request and three-rule checks were too heavy).

## 3. Constraints

- AGENTS.md contracts: flags come from code-controlled trace data; planted defects visible in the trace, not explained in comments; traces named `activity-<n>-...`; one session per activity run; flush at the end; reusable logic in `experiment_utils.py`; changes split into pieces of at most 3 files.
- Agenda fixed: Mini-Game 1 35 min, 2 20 min, 3 20 min, 4 40 min, demos 30 min, plus breaks.
- Solo, remote game master. Teams post claim codes in a form; the game master shares a screen.

## 4. Approaches

| | Approach | Trade-off | Decision |
|---|---|---|---|
| **A** | `check_flag` gates the next clue: a correct answer prints the next briefing and opens the next door; gated cells stay locked with a joke until then. Where natural, the answer is also the next run's input. Briefings live in plain text in `game.py`. | Small change on existing machinery, readable and fixable live; a curious reader of `game.py` can skip ahead | **Chosen** |
| B | Encrypted Mini-Games: each briefing and its parameters encrypted with the previous answer | A real lock, maybe a fun side quest; opaque generic cells, hard to fix live, machinery that teaches nothing about observability | Rejected |
| C | No lock: the answer is the next input, a wrong answer gives a useless trace | Zero lock code; does not fit every step, and teams can skip by guessing | Folded into A where it fits |

Structure chosen with the game master: **four Mini-Games with a vault**, not one strict chain (a strict chain blocks stuck teams and breaks the time slots).

## 5. Game mechanics

### 5.1 Doors and keys
- `check_flag(clue, guess)` on a correct answer: records the clue as solved for the team in `.game_state.json` (already used for hints), prints a funny solved line, the claim code, and **the next clue's briefing**.
- `open_door(clue)` returns `True` when the previous clue is solved and prints that clue's briefing again; otherwise prints a locked joke and returns `False`. Gated cells read `if open_door("1-2"): ...` so a locked notebook executes to the end without raising.
- State lives in the file, not a variable, so a kernel restart does not lock a team out (my call).
- Notebook Markdown for a locked clue shows only a teaser title (`🔒 Clue 2 — ???` plus one funny line); the real briefing comes from `game.py`.
- Wrong guesses stay free and get a rotating, gentle roast.

### 5.2 Mini-Games, clues and fragments
- Each Mini-Game: three chained clues (Mini-Game 1 also has an orientation clue) and a vault fragment printed when its last clue is solved.
- Fragments in order: Mini-Game 1 `skye`, 2 `is`, 3 `back`, 4 `online` → vault answer `skye-is-back-online`.
- The vault is the last cell of `notebook-4-tool-calling.ipynb` (`check_flag("vault", ...)`): an ASCII celebration and a claim code. No fifth notebook.
- **Fragments may be shared between teams.** A stuck team can ask another team for its fragment and still open the vault. Clue points remain earned only by solving the clue.

### 5.3 Hints
- `hint(clue)` as today, max 2 per clue, each costs **10%** of the clue's points (was 25%). Hint text is a nudge with a joke, never the answer.

### 5.3a Stuck teams
- The game master gives the answer by hand (decided by the game master). No rescue or skip function.
- Before giving it, the game master asks the team to use both hints, so the claim code scores the clue as a two-hint solve (80 pts) without new machinery (my call).
- `MENTORS.md` "Unblocking without spoiling" gains this as the last step: give the answer when a team has been stuck on one clue for about 8 minutes (my call).

### 5.4 Points (secondary)
- Every clue 100 points, flat. Orientation clue 50. Hidden bonus `1-B` 100. Vault 200.
- **Good-colleague points:** a team that escaped a Mini-Game may help a stuck team by pointing at the right step, never the answer. The game master awards +50 per help on trust, in a `kudos` tab of the sheet.
- Claim codes, the form and the `key` tab work as today; `make_claim_table.py` generates the new rows.

### 5.5 Shared recovery meter
- The sheet gets a `meter` tab: distinct Mini-Game-escape claims (last clue of each Mini-Game) across all teams ÷ (teams × 4), shown as a big progress bar (for example a `SPARKLINE` bar in Google Sheets). This, not the ranking, is what the game master shares during play.
- Milestone memos scripted in `MENTORS.md` for 25/50/75/100%, short absurd updates from fictional Skyline Travel staff (for example "The rooster has been asked to stop crowing at the gate. It declined."). Story only, no unlocks.

### 5.6 Final score and post-mortem
- Demos become an **incident post-mortem**: each team presents the root cause of one Mini-Game, assigned so all four are covered (with more than four teams, Mini-Games repeat).
- Rubric (0/1/2 each, 10 total): Evidence (walks through a real activity log), Root cause (one sentence a colleague who was not there understands), Proof (before/after pair), Cost or speed (one number from the logs and what drove it), Clarity for the group (would another team now fix this in their own code?).
- Final score = 50 × (team points incl. kudos ÷ highest) + 50 × (rubric ÷ 10). Tie-break: earlier vault claim. The ranking is shown once, at the end.

## 6. Mini-Game designs

Common to all: plain language for engineers new to LLMs; each notebook's opening Markdown keeps the AGENTS.md purpose block (purpose, expected observation, bad practice, good practice, why it works, deliverable), rewritten in the new tone, plus a three-line **Rosetta stone** mapping the Mini-Game's LLM terms to monolith terms (examples: retrieval = the query your service runs before rendering a page; system prompt = the config file nobody reads; tool call = an RPC the model decides to make; tokens = payload bytes you are billed for). Trace names keep `activity-<n>-...-l<level>-<variant>`; step names may get story flavor where noted.

**Data.** `data/travel_corpus.json` is rewritten around the stories: a lost-and-found log (Mini-Game 1), the influencer's rebooking requests (Mini-Game 2), the animals-on-board notices including a retired one (Mini-Game 3), and bookings (Mini-Game 4). Fare tiers and membership policies are removed. Record texts are part of the comedy.

**Cast** (fictional; names are the builder's call): a proud fisherman, a travel influencer, a farmer with his rooster, an elderly lady with a grand piano. Cameos cross Mini-Games (the rooster turns up in the lost-and-found log, the fisherman's booking turns up in the piano lady's lookup). The joke is always the situation, never the person. In participant text the bird is a "rooster".

All flags are new unless marked *kept*. Exact ids below are proposals; the builder may rename them, but each must stay a code-controlled value visible in the named trace step.

### Mini-Game 1 — Something Smells Fishy (search; Case 1, 35 min)
A fisherman lost his bag of fresh-caught fish on his flight and asks Skye whether it was found. Skye searches the lost-and-found log.
- **1-0 Orientation (50 pts).** Find the name of the step that searched the log. Flag: `activity-1-retrieval` (*kept* step name).
- **1-1 The wrong item.** Without a flight filter, the search returns another flight's item: a live rooster found in row 12, very loud. Find its id. Flag: e.g. `lf-rooster-sk205`. Fix shown: filter by the customer's flight; the filtered run returns the fish bag.
- **1-2 Two things lost.** He also lost his lucky fishing hat; the search hands Skye only the top result. Find the id of the item Skye never saw. Flag: e.g. `lf-fishing-hat-sk101`. Fix: more results.
- **1-3 Play it safe, pay for it.** A colleague "fixes" search by pasting the whole lost-and-found log into every question. Find how many log entries were sent. Flag: the log size (code-controlled count). Fragment `skye`.
- **1-B Hidden bonus.** A `detective_note` in the search step's metadata, never gated. Flag: e.g. `golden-fishhook`.
- The question text doubles as the search query in 1-2: the builder verifies the keyword search ranks the items so the flags come out as designed.

### Mini-Game 2 — The Cockpit Selfie (format; Case 2, 20 min)
A travel influencer wants to rebook so she can take a selfie with the pilot mid-flight. The booking system only accepts a structured booking.
- **2-1 The prose problem.** Her request summarized in free text is rejected. Flag: the reason code, `not_an_object` (*kept*).
- **2-2 Three messy requests.** Three of her messages run as separate steps: one clean, one with a relative date ("the day after my next video goes viral"), one asking for the seat "cockpit, next to the pilot". Find the field the booking system cannot hold for the cockpit request. Flag: `cabin` (*kept*). (Batch shrinks from five to three requests; the clean one and the two defects stay code-checkable.)
- **2-3 Make the booking system happy.** The team writes instructions so all three answers are usable (the clean one books, the other two ask back for `travel_date` and `cabin`). Achievement flag printed when all three pass: e.g. `three-for-three`. Fragment `is`.

### Mini-Game 3 — Cock-a-Doodle-Don't (wrong answers; Case 3, 20 min)
A farmer wants to fly with his rooster so it can wake him at dawn at the destination. Skye says yes. A cabin full of sleeping passengers disagrees.
- **3-1 The hidden instruction.** Skye's instructions, visible only in the answer step, say something like "Never disappoint a farmer: farm animals always get a window seat." Find what the instructions promise the rooster. Flag: e.g. `window-seat`.
- **3-2 Faithful to an old notice.** With good instructions Skye still says yes: the search returned the old pets notice, which allowed small birds in the cabin and was retired after "an incident at dawn" (status and end date visible in the search step). The current notice says no birds in the cabin. Find the old notice's id. Flag: e.g. `pets-notice-old`. Fix: search only current notices.
- **3-3 Write the rule.** The broken instructions are still sent first; the team adds instructions so Skye politely refuses the rooster in the cabin. The harness asks two or three of the farmer's questions with code-checkable answers (for example cabin: no; cargo hold fee: a fixed number from the current notice). Achievement flag: e.g. `quiet-flight`. Fragment `back`. Flavor text in these questions must not contain the numbers or words the checks look for.

### Mini-Game 4 — The Piano Has Left the Building (broken tool; Case 4, 40 min)
An elderly lady checked in her grand piano and asks Skye where it is. Skye looks up her booking with a tool.
- **4-1 The wrong label.** The tool reads a detail the assistant never sends. Flag: `booking_id` (*kept*).
- **4-2 The wrong trip.** A "forgiving" lookup never fails and falls back to the first booking: she is told her piano is a bag of fish, which is the fisherman's booking. Find the reference that came back. Flag: the fisherman's booking reference, e.g. `sky-3310` (*kept* value). Solved briefing: the fisherman is now confused why his fish weighs 400 kg.
- **4-3 The slow lookup.** The lookup confirms with the piano movers' system; a cache key with the current time never hits, so it checks three times. Step renamed to `piano-mover-check`. Flag: `piano-mover-check-3`. Fragment `online`.
- **Vault.** Flag: `skye-is-back-online` (200 pts).

## 7. What changes in the repository

One branch, pieces of at most 3 files as sequenced commits; the repository only needs to be consistent at the end of the branch, where the full verification (§8) runs. Start from `HEAD`: the uncommitted test-play changes in `notebook-1-rag.ipynb` are discarded (decided by the game master). In order:

0. `AGENTS.md`: agenda outcomes, the four activity descriptions, audience wording, shipped-output rule below.
1. `data/travel_corpus.json` (story data), `game.py` (clues, briefings, lock and wrong-guess lines, fragments, `open_door`, solved state, points, hint cost), `make_claim_table.py`. Verify: `make_claim_table.py` runs.
2. `experiment_utils.py` + `notebook-1-rag.ipynb`.
3. `experiment_utils.py` + `notebook-2-output-format.ipynb` + `notebook-3-hallucination.ipynb`.
4. `experiment_utils.py` + `notebook-4-tool-calling.ipynb` with the vault cell.
5. `README.md`, `MENTORS.md` (meter, milestones, kudos, post-mortem assignment, answers, run of show).

Notebook file names stay (they are listed in AGENTS.md and README); titles inside say "Mini-Game".

Shipped notebooks: committed with outputs from a run where every door is still locked after the first clue. This changes AGENTS.md's "outputs that show the comparison" rule to "outputs up to the first door" (my call, because full outputs would spoil the chain).

## 8. Verification

- Headless execution of each notebook with placeholder guesses finishes without errors (locked doors print, do not raise).
- A scratch run with every correct answer typed in opens every door, prints every briefing and fragment, opens the vault; each clue's flag evidence is visible in the trace step it points at; Mini-Game 3 and 4 defects reproduce before the fix and disappear after.
- `make_claim_table.py` succeeds and its row count matches the clue list.

## 9. Left to the builder

- All funny text: record texts, briefings, lock lines, wrong-guess roasts, solved lines, milestone memos, hint wording, character names (within §2 anti-goals).
- Exact ids of flag-bearing records, as long as they stay code-controlled and visible in the named step.
- Exact Rosetta-stone lines; exact sheet formulas for the `meter` and `kudos` tabs.
- How the scratch "all answers" verification run is done (for example an uncommitted copy of the notebooks with answers filled in).

## 10. Calls I made (check these)

- Door state lives in `.game_state.json` (`open_door`), not a returned key variable.
- Orientation clue `1-0` (50 pts) to flatten the start.
- Flat 100 points per clue, 10% per hint, vault 200, bonus 100, kudos +50 per help.
- Vault phrase `skye-is-back-online`, vault cell at the end of notebook 4; fragments shareable between teams.
- Final score 50/50 points vs post-mortem; ranking shown only at the end.
- Shipped notebooks show outputs only up to the first door.
- Mini-Game 2 batch shrinks from five requests to three; Mini-Game 3's rule check to two or three questions.
- "Rooster" in participant text; the rooster cameos as the wrong lost item in Mini-Game 1, the fisherman's booking as the wrong trip in Mini-Game 4.
- Partner-system step renamed `piano-mover-check`.
- Stuck teams: both hints first, then the game master's answer (scores 80); give it after about 8 minutes stuck.
- One branch with sequenced commits, consistent at the end; `AGENTS.md` updated first.
