# Skyline Travel: Pick the Winner, self-contained stories, plain English — design

Builds on `2026-11-20-langfuse-missions-design.md`. Keeps its mechanics (run → act in Langfuse → `check()`), its anti-goals and its check rules. Adds a second mission kind, rewrites the participant-facing text, and makes each activity's story self-contained.

## 1. Intent and the why

The game master reviewed the missions build and likes the format: take an action in Langfuse, validate it in the next cell. Setup is easy and the code is clean. What needs work:

- The notebooks talk about "monolith people" and "a colleague". Participants' background must not appear in the notebooks.
- The jokes are hard to follow. The text should read at a teenager's level of English: goofy and comic, but friendly and professional.
- The first comment (mission 1.1) is clunky: find a step, select it, find its 💬 button.
- More missions of the "compare two runs and choose" kind, each one a step in the character's story.
- Stories leak into each other: Activity 3's rooster is Activity 1's wrong item; Activity 4's wrong booking is Gus's fish; Coco's ring light sits in Gus's lost-and-found log. Each activity must be its own story.
- Each main character should have an exaggerated, fun personality.
- The model's user message mixes the customer's words and the retrieved context; delimit them with Markdown so a reader of the trace Input sees each part.

## 2. Goals, non-goals, anti-goals

Goals
- Four new **Pick the Winner** missions per activity (16 total), plus the existing 1.4 turned into one.
- Every activity uses only its own character, items, animals and data.
- Every notebook Markdown cell rewritten in simple, goofy-but-professional English; no "Rosetta stone", no "Monolith reflex", no colleagues, no participant background.
- Mission 1.1 becomes a warm-up comment on the whole trace (top node), not on a step.
- User messages that carry retrieved context use Markdown headings.
- Agenda times updated.

Non-goals
- No change to the four activities, their order, or the existing fix missions' mechanics (except 1.1 and 1.4, below).
- No points, ranking, typed answers or locks.
- No new service, no new dependency.

Anti-goals (failure even if it works)
- A Pick the Winner pair where the better option is not visible in Langfuse, or is visible in the notebook output.
- A trace or option name that gives away the winner.
- A check that reads comment text, model wording or token counts.
- An item, character or animal of one activity appearing in another activity's trace, data or text (the final `SKYE_IS_BACK` banner in `report()` is the one allowed place that names all four stories).
- Jokes that need cultural background or wordplay a non-native teenager would miss.

## 3. Constraints

- AGENTS.md contracts apply: trace names `activity-<n>-...`, one session per run, flush, real model calls through `langfuse.openai`, reusable logic in `experiment_utils.py`, notebooks ship with cleared outputs, no cell raises, at most 3 files per change.
- Missions, planted defects, seeded prompts and observation names are participant-facing contracts: notebooks, `experiment_utils.py`, README and `MENTORS.md` change together (across sequenced changes).
- Langfuse server 4.80 self-hosted, Python SDK 5.2. One inference endpoint (`OPENAI_MODEL`); no second model to compare.

## 4. Approaches

**Comparison mission form** (decided by the game master)
| | Approach | Decision |
|---|---|---|
| **A** | Pick the winner: two runs in one session, comment on the one you would ship | **Chosen**: no new mechanics, code-checkable by where the comment sits |
| B | Grade both with the `correct` score | Rejected: more clicks; scores stay in 4.2 |
| C | Spot the guilty step | Rejected: what missions already do |

**How the duels are built** (decided by the game master)
| | Approach | Decision |
|---|---|---|
| **A** | One table-driven `run_duel("<mission>")` reusing each activity's pipeline with per-option overrides; one generic check | **Chosen**: one runner instead of 16 near-copies |
| B | One run function per mission | Rejected: ~500 lines of repetition |
| C | Pre-written answers logged as fake generations | Rejected: breaks the `langfuse.openai` contract; traces would lie |

**Scope** (decided by the game master): widened from notebooks only to data, `experiment_utils.py`, README, `MENTORS.md`, AGENTS.md. Work goes one activity at a time.

**Count** (decided by the game master): four new duels per activity, every activity.

## 5. The design

### 5.1 Pick the Winner mechanics

- A duel cell is `run_duel("1.5")`. It prints one status line and a 📎 link to the session (not to one trace), e.g. `🥊 Two Skyes answered Gus. Only one should keep the job.`
- One session per duel run: `activity-<n>-duel-<mission>-<RUN_ID>-<4 hex>`, tagged `activity-<n>`.
- Two traces per session, named `activity-<n>-duel-<mission>-option-a` and `...-option-b`. Inside, the same step names as the activity's main pipeline (`activity-1-retrieval`, `activity-1-generation`, ...), plus any extra step the duel needs.
- Each trace's root records facts: `{"mission", "option"}` plus whatever the duel's planted gap is (e.g. `max_tokens`, `search`, `tool_calls`).
- The winning letter is fixed per mission and alternates across missions (not always B). Winners live in the duel table and in `MENTORS.md`.
- Duels use their own fixed settings, never the team's `production` prompt config, so they work in any order and before the fix missions.
- Where the two options differ in prompt text, the text is a seeded Langfuse prompt `duel-<mission>` with two versions labelled `option-a` and `option-b`, so the answer step links to a real prompt version. Seeded only when missing, never overwritten.
- Mission briefing shape: story beat, "In Langfuse" steps (open the session, open both traces, look at X), Stuck block, `check()`. The last step is always: "Click the **top line** of the run you would ship and leave a comment."

**Check (`_check_duel`)**
- ✅ when at least one session of that mission has a comment on the winner's top node and none on the loser's.
- Comment on the loser only → ❌ with the mission's hint ("Look at the Timeline of both runs. Gus has 10 minutes.").
- Comments on both in every session → ❌ "Skye can only ship one. Pick one run."
- No comment → ❌ "Open the session, compare the two runs, comment on the one you'd ship."
- Uses `has_comment`-style lookups scoped per session (trace's `session_id`); a comment on any step inside a trace does not count, with the existing "that's a step, use the top line" nudge.
- Mixed sessions (winner-only in one, loser-only in another) count as ✅: one clean pick anywhere is enough (my call; progress is not ranked).

**Duels are bonus** (decided by the game master: "make it simple"; people play solo or in small groups, in the room and online). The fix missions (1.1–1.3, 2.1–2.2, 3.1–3.2, 4.1–4.3) are the core: they alone unlock `SKYE_IS_BACK`. `report()` prints the core missions as today, then one line `🥊 Pick the winner: <n> of <m>`, and lists each duel ✅/❌ under it. 1.4 becomes a duel and so leaves the core. A person who runs out of time skips duels and still finishes.

### 5.2 Characters

| Activity | Character | Personality |
|---|---|---|
| 1 | Gus Haddock, fisherman | Names every fish (the lost bag holds Big Bertha), turns everything into a fishing story, yells "HOLY MOLY!", slips into Norwegian when excited |
| 2 | Coco Glow, influencer | Follower count goes up in every message (2.3M, 2.4M…), says "literally", rates everything out of 10, calls Skye "bestie" |
| 3 | Farmer Barnaby | Treats Sir Crowsalot like royalty, says "OH MY STARS!" and talks about the weather a lot, awake since 4 a.m., TYPES IN CAPS |
| 4 | Edna Ivory, 87 | Retired concert pianist, calls everyone "dear", extremely polite and slightly terrifying; the piano is called Ludwig |

### 5.3 Missions per activity

Existing fix missions keep their numbers, defects and fixes; their text is rewritten. New duels follow them, as one story event after another.

**Activity 1 — Something Smells Fishy (45 min)**
- 1.1 *Say hi to the trace* (changed): open the link, read the answer step's Input and Output, then click the **top line of the tree** and leave any comment there. Check: comment on the `activity-1-rag` root.
- 1.2 *Who invited the dolphin?*: the wrong-flight item is now **Finnegan, a live dolphin in an inflatable paddling pool, found on SK205** (replaces the rooster). It must outrank the fish for the unfiltered `top_k: 1` search. Check unchanged except the item id.
- 1.3 *The hat nobody saw*: unchanged (hat, rubber duck stay).
- 1.4 *Pick the winner: the whole log* (changed): filtered search vs. pasting the whole log. Winner: filtered (same answer, far fewer tokens). Moves to `run_duel("1.4")`; the old `activity-1-rag-filtered` / `activity-1-rag-send-all` names go away.
- 1.5 *The desk closes in 10 minutes*: one option has an extra slow step `double-check-with-desk`. Winner: the fast one. Look at: Timeline, latency column.
- 1.6 *Directions to the desk*: one option has `max_tokens` small enough to cut the answer mid-sentence. Winner: the complete one. Look at: answer Output, output tokens, model parameters.
- 1.7 *Is Big Bertha still fresh?*: one option searches the log (an entry says the ice melted at 09:00), the other skips the search and is told to sound confident. Winner: the one with the search. Look at: whether the search step exists and what it returned.
- 1.8 *HOLY MOLY, in Norwegian*: Gus writes in Norwegian. `duel-1.8` prompt: one version says "always answer in English", the other "answer in the customer's language". Winner: customer's language. Look at: the prompt version linked on each answer step.

**Activity 2 — The Cockpit Selfie (30 min)**
- 2.1, 2.2: unchanged mechanics, rewritten text.
- 2.3 *The packing list*: a `baggage-system` step validates a JSON packing list. `duel-2.3`: one version asks for the exact JSON, the other for "a fun bullet list with emojis". Winner: accepted by `baggage-system`.
- 2.4 *The caption*: a `caption-check` step enforces 150 characters. `duel-2.4`: "long, heartfelt caption" vs "max 150 characters". Winner: passes the check.
- 2.5 *Rate your flight*: a `feedback-form` step accepts a whole number 1–5. `duel-2.5`: one version lets Coco's style through ("11/10, iconic"), the other states the form's rule. Winner: accepted.
- 2.6 *Going live*: a `privacy-check` step flags a booking code in the reply (regex, code-checked). `duel-2.6`: "include all booking details" vs "never show the booking code". Winner: no leak.

**Activity 3 — Cock-a-Doodle-Don't (30 min)**
- 3.1, 3.2: unchanged mechanics, rewritten text. Notices contain only animal notices.
- 3.3 *The crate size*: one option searches the notices, the other skips the search. Winner: the grounded one. Look at: search step present, numbers in the answer vs. notice.
- 3.4 *"Never say I don't know"*: a question the notices cannot answer (e.g. can Sir Crowsalot earn air miles). `duel-3.4`: one version forbids "I don't know", the other allows it. Winner: honest.
- 3.5 *The feed limit*: one option's search returns the notice cut off before the weight limit (a chunking bug, visible in the retrieval Output), so Skye guesses; the other gets the whole notice. Winner: the whole notice.
- 3.6 *Official crew member*: Barnaby asks for a certificate making the rooster crew. `duel-3.6`: one version has no "only state what the notices say" rule, the other has it. Winner: declines politely.

**Activity 4 — The Piano Has Left the Building (50 min)**
- 4.1–4.3: unchanged mechanics, rewritten text. In 4.2 the non-strict lookup returns another Edna-world booking (**Ludwig's piano stool**, a separate booking), not Gus's fish. Bookings contain only Edna's.
- 4.4 *Piano tuning*: the tool says "still checking, ask again"; one option has no one-lookup limit and calls it 4 times, the other once. Winner: one call. Look at: number of `get_booking` steps, Timeline.
- 4.5 *"Thank you, dear"*: Edna only says thanks. One option forces a tool call (`tool_choice="required"`), the other uses `auto`. Winner: no tool call. Look at: generation parameters, the extra step.
- 4.6 *The insurance claim*: the tool returns an error. `duel-4.6`: "never upset Edna, always reassure" vs "tell the truth kindly". Winner: honest about the error. Look at: tool Output vs. answer.
- 4.7 *Track or cancel?*: two tools, `track_shipment` and `cancel_booking` (fake: it only returns "Ludwig's trip cancelled"). One option has vague, swapped-sounding tool descriptions, the other clear ones. Winner: calls `track_shipment`. Look at: tool definitions in the generation Input, which tool step ran.

### 5.4 Self-contained data

- `data/travel_corpus.json` is grouped by activity (`activity_1`, `activity_2`, ...); each activity's code reads only its own group.
- Removed from Activity 1: rooster, ring light, trombone, bagpipes, telescope "pointed at the cockpit". Added: Finnegan the dolphin (SK205), a melted-ice entry for 1.7, items for 1.4's "whole log" that are absurd but story-neutral.
- Activity 3 notices: animal notices only (instrument and cockpit notices removed), plus a crate-size notice and a feed-limit notice for the duels.
- Activity 4 bookings: Edna's only (piano, piano stool, any duel bookings).

### 5.5 Delimited user messages

Where a user message carries retrieved context:

```
## Customer message
<the customer's words>

## Lost-and-found entries (search results)
- ...
```

Activity 3 uses `## Retrieved notice`. Messages without context (Activities 2 and 4) stay as the customer's words only.

### 5.6 Language rules for all participant text

Applies to notebook Markdown and to check/solved messages in `experiment_utils.py`.
- Short sentences, everyday words. Explain trace, step, generation, session, prompt version the first time each appears, in one plain sentence.
- The joke is the situation and the character, never the reader. No puns that need native English, no cultural references.
- No rare or specialist words, even in a character's catchphrase or a fish's name: "HOLY MOLY!", not "HOLY MACKEREL!". If a teenager would have to look a word up, swap it for a common one.
- Notebook header cell keeps the required sections (purpose, what to expect, bad practice, good practice, why, deliverable), rewritten.
- Remove every "Rosetta stone for monolith people" block and every "Monolith reflex" line; no mention of colleagues or the participants' background.

### 5.7 Docs

- AGENTS.md agenda table: Activity 1 45 min, 2 30 min, 3 30 min, 4 50 min; outcomes mention picking winners. Story list in the scope paragraph updated (the dolphin, not the rooster, in Activity 1's data).
- **A simple end of the day** (decided by the game master: one facilitator, some people in the room, some online alone). Team demos, voting and open exploration are removed. The new run of show, about 3.5 h like today:

  | Slot | Min |
  |---|---|
  | Kickoff (live-play 1.1 on screen) | 15 |
  | Activity 1 | 45 |
  | Break | 10 |
  | Activity 2 | 30 |
  | Activity 3 | 30 |
  | Break + mid-point check (`report()` on screen) | 10 |
  | Activity 4 | 50 |
  | Wrap-up: everyone runs `report()`; a few volunteers, in the room or online, show one before/after pair; takeaways | 20 |

  Total 210 min (was 230). Deliverables shrink to "core missions ✅ and one before/after pair you can show". Solo players need no team, no assignment and no vote.
- README activities table: mission ranges (1.1–1.8, 2.1–2.6, 3.1–3.6, 4.1–4.7) and "How to play" gains a "Pick the winner" line.
- `MENTORS.md`: winner and reason for every duel; changed 1.1, 1.2, 1.4, 4.2 answers; the new run of show (no demo assignment, no voting); mentor cues re-timed to the new activity lengths.

### 5.8 Order of work

One activity per change, at most 3 files each:
1. Activity 1: `data/travel_corpus.json` (its group), `experiment_utils.py` (duel runner, duel check, Activity 1), `notebook-1-rag.ipynb`.
2. Activity 2: data, `experiment_utils.py`, notebook 2.
3. Activity 3: data, `experiment_utils.py`, notebook 3.
4. Activity 4: data, `experiment_utils.py`, notebook 4.
5. Docs: AGENTS.md, README, `MENTORS.md`.

The corpus regrouping happens in step 1 for all groups (moving existing entries only) so later steps only add.

## 6. Verification

- Each activity: execute its notebook headlessly in a fresh kernel (no cell raises; checks print ❌).
- Each duel: run it at least 3 times and confirm in Langfuse that the planted gap shows every time (especially 1.7, 3.3, 3.5, 4.6, 4.7, which depend on model behavior). Strengthen the losing option's setup until it does.
- Each duel check: ❌ with no comment, ❌ with the loser commented, ❌ with both, ✅ with the winner only.
- Changed fix missions (1.1, 1.2, 1.4, 4.2): defect reproduces before the fix, disappears after, check turns ✅.
- Grep every activity's trace inputs and notebook text for other activities' characters and items.

## 7. Left to the builder

- Exact wording of stories, briefings, nudges and solved messages, within §5.6.
- The winning letter per duel (alternating), the slow step's duration (long enough to stand out in the Timeline, short enough not to bore: about 5–8 s), `max_tokens` for 1.6, the chunk cut for 3.5.
- Duel table shape and field names in `experiment_utils.py`.
- Whether duel step names reuse the activity's names exactly or add a suffix, as long as the main pipeline's names are unchanged.

Settled as my calls after the builder check (correct me if wrong):
- Duels whose two options share a system prompt use fixed, defect-free text, never `skye-animals` v1 or `skye-piano` v1, so they don't spoil 3.1 or 4.1.
- The 1.7 melted-ice entry must not outrank the hat in Gus's filtered search; 1.3's fix keeps working with `top_k: 3`.
- Coco's booking code in 2.6 comes from her own booking in Activity 2's data, passed in the user message.
- The 4.4 one-lookup limit is in code (like today's "one lookup per question" reply), not in prompt text.
- The corpus regroup in step 1 moves Activity 2–4 entries untouched; the cross-story items they still carry (Gus's fish booking in Activity 4) are removed in their own activity's step.
