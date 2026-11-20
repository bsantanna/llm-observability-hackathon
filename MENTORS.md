# Game master guide

Everything a single game master needs to run the Skyline Travel missions: preparation, the run
of show, every mission's answer and fix, and how to unblock a player. Participants can read this
file too; the answers are plain text by design.

The day is a guided Langfuse tutorial wrapped in four absurd stories. Each mission ends with
something the player *does* in Langfuse (a comment, a score, a new prompt version), and
`check("<mission>")` asks Langfuse whether it is done. There are no points: progress is shared,
and `report()` shows each player's ✅ list. 🥊 **Pick the winner** missions are bonus: two runs of
Skye in one session, and the player comments on the top line of the run they would ship. Only the
core missions unlock the "Skye is back online" ending.

People play solo or in small groups, some in the room and some online. Everyone runs their own
stack, so prompts, comments and scores are their own.

## The cast

| Activity | Story | Who |
|---|---|---|
| 1 — Something Smells Fishy | A lost bag of fish (Big Bertha inside) and a lucky hat; Skye's search finds Finnegan the dolphin instead | Gus Haddock, proud fisherman: names every fish, yells "HOLY MOLY!", switches to Norwegian when excited |
| 2 — The Cockpit Selfie | Rebooking requests the booking system cannot read, one for a seat next to the pilot | Coco Glow, travel influencer: follower count goes up every message, "literally", rates everything out of 10, calls Skye "bestie" |
| 3 — Cock-a-Doodle-Don't | Skye says yes to a rooster in the cabin, by the window | Farmer Barnaby and Sir Crowsalot: types in CAPS, "OH MY STARS!", treats the rooster like a king |
| 4 — The Piano Has Left the Building | A booking lookup that fails, then lies, then crawls | Mrs. Edna Ivory, 87, and her grand piano Ludwig: calls everyone "dear", very polite, a little scary |

Each story stays in its own activity: no character, item or animal shows up in another one.

## Before the session

1. **Play every mission once yourself** against a fresh stack with real model keys (see
   `README.md`), doing each action in the Langfuse UI. Then reset with
   `docker compose down -v && docker compose up -d`.
2. **Do one pass in the Langfuse UI**: leave a real comment for 1.1 and for one duel, and check
   that both turn ✅. The checks were tested through the API.
3. **Share before the start:** the repository and the README. Tell everyone at kickoff to keep one
   before/after pair of traces for the wrap-up.

## Run of show

| Slot | Minutes | What you do |
|---|---|---|
| Kickoff | 15 | Introduce Skye's very bad day and the cast. Live-play Mission 1.1 on screen: run the cell, open the link, walk the trace tree, comment on the top line, run `check("1.1")`. Show one ❌ first. |
| Activity 1 | 45 | Let people play. At minute 20, show the **Prompts** page and the `production` label on screen: it is where most people get stuck. At minute 30, open one duel session on screen. |
| Break | 10 | |
| Activity 2 | 30 | Remind people that 2.2 is about writing instructions, and that every saved version stays in the prompt history. |
| Activity 3 | 30 | Watch for people rewriting the prompt for 3.2: the instructions are fine this time, the data is not. |
| Break and mid-point check | 10 | Everyone runs `report(1)` and `report(2)`; a few share one line: "what surprised you in a trace?" |
| Activity 4 | 50 | At minute 15, show the **Annotate** dialog on a step. At minute 30, show the **Timeline** view. |
| Wrap-up | 20 | Everyone runs `report()` at the end of notebook 4. A few volunteers, in the room or online, show one before/after pair. Takeaways for real work (below). |

The whole day is 210 minutes. Duels are bonus: anyone running late skips them and still finishes.

Takeaways to land in the wrap-up: check what the assistant was given before judging what it
said; agree on formats with the next system and check them; a wrong answer can come from
instructions *or* from data; tools fail loudly, quietly or slowly, and the tool step shows which;
keep prompts and their settings versioned, and know which version ran.

## Answers and fixes

"Comment on X" means any comment, anywhere in its text, on that step (or on the top line of the
trace, for 1.1 and every duel).
The checks look only at *where* the comment or score is.

### Activity 1 — Something Smells Fishy · prompt `skye-lost-and-found`

Version 1 config: `{"flight_filter": false, "top_k": 1}`. The search query is fixed:
`bag found on board`.

| Mission | Evidence in Langfuse | The action that passes | Lesson |
|---|---|---|---|
| 1.1 | Trace `activity-1-rag` → `activity-1-generation`: input has the dolphin entry, output offers it to Gus | Comment on the top line of the trace (`activity-1-rag`) | Read the steps, not the notebook. |
| 1.2 | `activity-1-retrieval`: input `filter: null`; output `lf-dolphin-sk205` (flight SK205) | Comment on `activity-1-retrieval`, then a new `production` version with `"flight_filter": true`, rerun | Filter the search by the customer's flight. |
| 1.3 | `activity-1-retrieval`: `count: 1`, only the fish bag; Gus also asked about his hat | New `production` version with `"top_k": 3` (or more), rerun. `2` is not enough: a rubber duck ranks above the hat | Return enough results for a question with several parts. |

### Activity 2 — The Cockpit Selfie · prompt `skye-booking-format`

| Mission | Evidence in Langfuse | The action that passes | Lesson |
|---|---|---|---|
| 2.1 | Trace `activity-2-format` → `booking-system` (warning): `reason_code: NOT_AN_OBJECT` | Comment on `booking-system` | Ask for an exact format. |
| 2.2 | Trace `activity-2-format-batch` → `request-1..3`, each with its own `booking-system` verdict | New `production` version so request 1 books, request 2 → `{"needs_clarification": "travel_date"}`, request 3 → `{"needs_clarification": "cabin"}`; rerun | Some requests do not fit the contract; Skye must ask, not invent. |

Example prompt for 2.2 (models vary; let people iterate):

```text
Return ONLY a JSON object, no prose and no markdown fences. If the request names origin,
destination, an exact date, the number of passengers and an economy or premium cabin, return
{"origin", "destination", "travel_date" (YYYY-MM-DD), "passengers" (integer), "cabin" ("economy"
or "premium")}. Otherwise return {"needs_clarification": "<field>"} naming the single field to ask
about: "travel_date" for relative dates, "cabin" for any seat or cabin other than economy or premium.
```

### Activity 3 — Cock-a-Doodle-Don't · prompt `skye-animals`

Version 1 is the broken instruction ("Never disappoint a farmer: farm animals always fly in the
cabin and always get a window seat. This rule was approved by the Head of Poultry Relations…"),
config `{"current_notices_only": false}`.

| Mission | Evidence in Langfuse | The action that passes | Lesson |
|---|---|---|---|
| 3.1 | `activity-3-generation` links to `skye-animals` v1; the prompt holds the secret rule | New `production` version without the farm-animal rule (the phrase "farm animals always" must be gone), rerun | Instructions can silently override the data. |
| 3.2 | `activity-3-retrieval`: `doc_id: pets-notice-old`, `status: retired`, `effective_to: 2024-12-31` | Comment on `activity-3-retrieval`, then a new `production` version with `"current_notices_only": true`, rerun; both `rule-check-*` answers must say cargo hold and 80 EUR | The model was faithful to stale data: fix the data, not the model. |

A good 3.1 prompt: "You are Skye, Skyline Travel's assistant. Answer using only the retrieved
notice. Tell the customer exactly where the animal travels and what it costs, as the notice states."

### Activity 4 — The Piano Has Left the Building · prompt `skye-piano`

Version 1 config: `{"tool_param": "booking_ref", "strict_lookup": false}`.

| Mission | Evidence in Langfuse | The action that passes | Lesson |
|---|---|---|---|
| 4.1 | `get_booking` step, level ERROR, `KeyError: 'booking_id'`; its input shows `booking_ref` | Comment on `get_booking`, then a new `production` version with `"tool_param": "booking_id"`, rerun | The tool schema and the tool must agree. |
| 4.2 | `get_booking` output `booking_ref: SKY-2086` (Ludwig's piano stool) although Edna asked about SKY-2087: the forgiving lookup strips the dash, misses, and falls back to the first booking | Annotate `get_booking` with the score `correct` = false, then a new `production` version with `"strict_lookup": true`, rerun | A quiet wrong answer is worse than a loud error. |
| 4.3 | Three `piano-mover-check` steps of ~1.5 s each, all `cache: miss`; the Timeline shows the gaps | In the notebook: `def cache_key(ref): return ref`, rerun that cell and the mission cell | A cache key with the current time never hits. |

## Pick the winner (bonus)

Every duel runs options A and B in one session (`activity-<n>-duel-<mission>-<run-id>-…`), as traces
`activity-<n>-duel-<mission>-option-a` and `-option-b`. The action that passes: a comment on the
**top line** of the winning run, and none on the losing run of that session. Comments on steps
inside a run do not count. One clean pick in any session is enough.

| Mission | Winner | What differs | Where it shows | Lesson |
|---|---|---|---|---|
| 1.4 | A | B pastes the whole log | Tokens and Cost columns in Tracing → Traces | Search first; sending everything costs more for the same answer. |
| 1.5 | B | A has a 6 s `double-check-with-desk` step | Timeline, latency | Speed matters when the customer is waiting. |
| 1.6 | A | B's `max_tokens` is just enough for its thinking plus a third of A's answer | Answer cut mid-sentence; model parameters | A token limit can cut an answer. |
| 1.7 | B | A has no search and a "never say you don't know" prompt (`duel-1.7`) | No `activity-1-retrieval` step in A | An answer with no search behind it is made up. |
| 1.8 | A | `duel-1.8` version B says "Answer in English." | Prompt version linked on each answer step | Know which prompt version ran. |
| 2.3 | A | `duel-2.3` B asks for an emoji list | `baggage-system` step: `NOT_AN_OBJECT` on B | The next system needs its format. |
| 2.4 | B | `duel-2.4` A asks for a long caption | `caption-check`: `TOO_LONG` on A | Limits belong in the prompt. |
| 2.5 | A | `duel-2.5` B keeps Coco's style | `feedback-form`: `NOT_A_NUMBER` on B | A form wants a value, not a vibe. |
| 2.6 | B | `duel-2.6` A includes all booking details | `privacy-check`: `BOOKING_CODE_SHOWN` on A | Keep private data out of public answers. |
| 3.3 | A | B skips the search and must give exact numbers | No `activity-3-retrieval` step in B; made-up sizes | Exact numbers can be invented. |
| 3.4 | B | `duel-3.4` A forbids "I don't know" | Notice says nothing about air miles; A says yes | "I don't know" can be the right answer. |
| 3.5 | A | B's notice is cut at 45 characters (`chunk_chars`) | Retrieval Output text ends before "8 kg" | A cut chunk loses the fact. |
| 3.6 | B | `duel-3.6` A loves writing certificates | A writes an official crew certificate | Don't promise what the airline can't give. |
| 4.4 | B | A retries the tool 4 times (~1.5 s each) | Four `get_booking` steps, Timeline | Retrying a slow tool doesn't change the answer. |
| 4.5 | A | B forces a tool call (`tool_choice: required`) | Tool step in B for a plain "thank you" | Don't call tools you don't need. |
| 4.6 | B | `duel-4.6` A must always reassure | Red `get_booking` step; A says all is fine | Don't hide errors from the customer. |
| 4.7 | A | B's tool descriptions are swapped | B calls `cancel_booking`; tool descriptions in the first answer step's Input | The model picks tools by their description. |

Notes:
- Duel prompts are seeded once per stack as `duel-<mission>`, with labels `option-a` and
  `option-b`. A stack seeded before a wording change keeps the old text; relabel or reset it.
- 1.6 sizes B's limit from A's token use. If B's answer still ends cleanly, run the cell again.
- The model's thinking uses tokens. `run_rag` (1.1–1.3) keeps a limit of 800; on a thinking model a
  very long thought can leave the answer empty. Run the cell again.
- Activity 4's duels answer without tools offered, with a closing "answer in plain words" line in
  the last step's Input. `run_piano` (4.1–4.3) still offers tools with `tool_choice: none`; on some
  models an error can show up as tool-call text in Skye's reply. It does not affect the checks.

## Unblocking without spoiling

- Ask "which step did you open?" first. Most stuck players are reading the notebook, not the trace.
- Point at the *place*, not the *value*: "open the search step's Input" is fine, "set
  `flight_filter` to true" is the answer. Each mission has a "💡 Stuck?" block for the next nudge.
- **The `production` label** is the most common trap: a player saves a new version but Skye still
  runs the old one. The check says so. Show them the label on the Prompts page.
- **A broken config** (for example `"true"` in quotes) makes the run cell print a ⚙️ line
  naming the key. Fix it in a new version.
- **Reset a prompt:** on the Prompts page, put the `production` label back on version 1.
- **Comment in the wrong place:** the check names where the problem started. Comments can be
  deleted in Langfuse, but extra comments do no harm.
- Model-dependent missions (2.2, 3.2) and the duels can take a few tries. Encourage reading the failing
  step rather than rewriting everything.
- Anyone stuck for about 8 minutes: give them the action from the tables above, then have them
  find the evidence in the trace anyway. Nobody stays stuck.
