# Game master guide

Everything a single game master needs to run the Skyline Travel missions: preparation, the run
of show, every mission's answer and fix, and how to unblock a team. Participants can read this
file too; the answers are plain text by design.

The day is a guided Langfuse tutorial wrapped in four absurd stories. Each mission ends with
something the team *does* in Langfuse (a comment, a score, a new prompt version), and
`check("<mission>")` asks Langfuse whether it is done. There are no points: progress is shared,
and `report()` shows each team's ✅ list.

## The cast

| Activity | Story | Who |
|---|---|---|
| 1 — Something Smells Fishy | A lost bag of fresh-caught fish; Skye's search finds a rooster instead | Gus Haddock, proud fisherman |
| 2 — The Cockpit Selfie | Rebooking requests the booking system cannot read, one for a seat next to the pilot | Coco Glow, travel influencer |
| 3 — Cock-a-Doodle-Don't | Skye says yes to a rooster in the cabin, by the window | Farmer Barnaby and Sir Crowsalot |
| 4 — The Piano Has Left the Building | A booking lookup that fails, then lies, then crawls | Mrs. Edna Ivory and her grand piano |

## Before the session

1. **Play every mission once yourself** against a fresh stack with real model keys (see
   `README.md`), doing each action in the Langfuse UI. Then reset with
   `docker compose down -v && docker compose up -d`.
2. **Share with teams before the start:** the repository and the README. Each team runs its own
   stack, so its prompts, comments and scores are its own.
3. **Assign demo activities**: one activity per team, so all four are covered (with more than
   four teams, repeat them). Tell teams at kickoff, so they keep a before/after pair of traces.

## Run of show

| Slot | Minutes | What you do |
|---|---|---|
| Kickoff | 15 | Introduce Skye's very bad day and the cast. Live-play Mission 1.1 on screen: run the cell, open the link, walk the trace tree, comment on the answer step, run `check("1.1")`. Show one ❌ first. |
| Activity 1 | 35 | Let teams play. At minute 20, show the **Prompts** page and the `production` label on screen: it is where most teams get stuck. |
| Break | 10 | |
| Activity 2 | 20 | Remind teams that 2.2 is about writing instructions, and that every saved version stays in the prompt history. |
| Mid-point check | 10 | Each team runs `report(1)` and `report(2)` and shares one line: "what surprised you in a trace?" |
| Activity 3 | 20 | Watch for teams rewriting the prompt for 3.2: the instructions are fine this time, the data is not. |
| Break | 10 | |
| Activity 4 | 40 | At minute 15, show the **Annotate** dialog on a step. At minute 25, show the **Timeline** view. |
| Wrap-up | 20 | Everyone runs `report()` at the end of notebook 4. Takeaways for real work (below). |
| Demos | 30 | About 3 minutes per team on its assigned activity: open a real trace, name the root cause, show before/after. |
| Voting and winners | 20 | The organizers vote on the demos. |
| Open exploration | 10 | Teams explore Langfuse freely: dashboards, sessions, prompt history. |

Takeaways to land in the wrap-up: check what the assistant was given before judging what it
said; agree on formats with the next system and check them; a wrong answer can come from
instructions *or* from data; tools fail loudly, quietly or slowly, and the tool step shows which;
keep prompts and their settings versioned, and know which version ran.

## Answers and fixes

"Comment on X" means any comment, anywhere in its text, on that step (or on the trace, for 1.4).
The checks look only at *where* the comment or score is.

### Activity 1 — Something Smells Fishy · prompt `skye-lost-and-found`

Version 1 config: `{"flight_filter": false, "top_k": 1}`. The search query is fixed:
`bag found on board`.

| Mission | Evidence in Langfuse | The action that passes | Lesson |
|---|---|---|---|
| 1.1 | Trace `activity-1-rag` → `activity-1-generation`: input has the rooster entry, output offers it to Gus | Comment on `activity-1-generation` | Read the steps, not the notebook. |
| 1.2 | `activity-1-retrieval`: input `filter: null`; output `lf-rooster-sk205` (flight SK205) | Comment on `activity-1-retrieval`, then a new `production` version with `"flight_filter": true`, rerun | Filter the search by the customer's flight. |
| 1.3 | `activity-1-retrieval`: `count: 1`, only the fish bag; Gus also asked about his hat | New `production` version with `"top_k": 3` (or more), rerun. `2` is not enough: a rubber duck ranks above the hat | Return enough results for a question with several parts. |
| 1.4 | Session of the send-all run: `activity-1-rag-send-all` sends all 16 log entries, about 2–3× the input tokens of `activity-1-rag-filtered` | Comment on the `activity-1-rag-send-all` **trace** (not a step) | Sending everything costs more for the same answer. |

### Activity 2 — The Cockpit Selfie · prompt `skye-booking-format`

| Mission | Evidence in Langfuse | The action that passes | Lesson |
|---|---|---|---|
| 2.1 | Trace `activity-2-format` → `booking-system` (warning): `reason_code: NOT_AN_OBJECT` | Comment on `booking-system` | Ask for an exact format. |
| 2.2 | Trace `activity-2-format-batch` → `request-1..3`, each with its own `booking-system` verdict | New `production` version so request 1 books, request 2 → `{"needs_clarification": "travel_date"}`, request 3 → `{"needs_clarification": "cabin"}`; rerun | Some requests do not fit the contract; Skye must ask, not invent. |

Example prompt for 2.2 (models vary; let teams iterate):

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
| 4.2 | `get_booking` output `booking_ref: SKY-3310` (Gus's fish) although Edna asked about SKY-2087: the forgiving lookup strips the dash, misses, and falls back to the first booking | Annotate `get_booking` with the score `correct` = false, then a new `production` version with `"strict_lookup": true`, rerun | A quiet wrong answer is worse than a loud error. |
| 4.3 | Three `piano-mover-check` steps of ~1.5 s each, all `cache: miss`; the Timeline shows the gaps | In the notebook: `def cache_key(ref): return ref`, rerun that cell and the mission cell | A cache key with the current time never hits. |

## Unblocking without spoiling

- Ask "which step did you open?" first. Most stuck teams are reading the notebook, not the trace.
- Point at the *place*, not the *value*: "open the search step's Input" is fine, "set
  `flight_filter` to true" is the answer. Each mission has a "💡 Stuck?" block for the next nudge.
- **The `production` label** is the most common trap: a team saves a new version but Skye still
  runs the old one. The check says so. Show them the label on the Prompts page.
- **A broken config** (for example `"true"` in quotes) makes the run cell print a ⚙️ line
  naming the key. Fix it in a new version.
- **Reset a prompt:** on the Prompts page, put the `production` label back on version 1.
- **Comment in the wrong place:** the check names where the problem started. Comments can be
  deleted in Langfuse, but extra comments do no harm.
- Model-dependent missions (2.2, 3.2) can take a few tries. Encourage reading the failing
  step rather than rewriting everything.
- A team stuck for about 8 minutes: give them the action from the table above, then have them
  find the evidence in the trace anyway. Nobody stays stuck.
