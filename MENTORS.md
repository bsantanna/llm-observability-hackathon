# Game master guide

Everything a single game master needs to run the Skyline Travel incident shift: preparation,
the scoreboard, the run of show, every answer, and the demo rubric. Participants can read
this file too. The answers are plain text by design, so the game runs on trust.

## Before the session

1. **Run every notebook once yourself** against a fresh stack with real model keys (see
   `README.md`), so the images are built and you have seen every level.
2. **Register team names.** Agree on the exact names in advance (for example
   `red-falcons`). Teams type them in the first cell of every notebook. Names are compared
   in lowercase with spaces turned into dashes.
3. **Generate the claim-code table:**

   ```bash
   .venv/bin/python make_claim_table.py red-falcons blue-otters green-lynx
   ```

   This writes `claim_codes.csv` (git-ignored). Each team gets 37 rows: 12 levels × 0–2
   hints, plus the bonus. The script refuses to run if an answer below does not match
   `game.py`, or if two teams' codes would collide (then rename a team).
4. **Build the form and scoring sheet** (next section) and test it with two codes from the CSV.
5. **Share with teams before the start:** the repository, the README, their team name, and
   the form link. Keep the form link out of the repository.

## Scoreboard: form and sheet

**Form** (any online form tool with a linked spreadsheet): two short-answer questions,
*Team* and *Claim code*. Responses land in a tab called `responses` with columns
A = Timestamp, B = Team, C = Claim code.

**Tab `key`:** paste `claim_codes.csv` (A = team, B = level, C = hints_used, D = claim_code,
E = points). Hide this tab.

**Tab `scores`** (formulas in row 2, written for Google Sheets; Excel 365 has the same
functions except `QUERY`, so use a PivotTable there):

| Column | Header | Formula (row 2) |
|---|---|---|
| A | code | `=UNIQUE(FILTER(UPPER(TRIM(responses!C2:C)), responses!C2:C<>""))` |
| B | team | `=IFERROR(XLOOKUP(A2, key!D:D, key!A:A), "UNKNOWN")` (fill down) |
| C | level | `=LEFT(A2, 3)` (fill down) |
| D | points | `=IFERROR(XLOOKUP(A2, key!D:D, key!E:E), 0)` (fill down) |
| E | first claimed | `=MIN(FILTER(responses!A2:A, UPPER(TRIM(responses!C2:C))=A2))` (fill down) |
| F | boosted | `=IF(AND($I$1<>"", C2="3-3", E2>=$I$1, E2<=$I$2), D2*2, D2)` (fill down) |
| G | counted | `=IF(F2=MAXIFS(F:F, B:B, B2, C:C, C2), F2, 0)` (fill down) |

Put the double-points window (optional twist) in `I1` (start) and `I2` (end) as date-times;
leave them empty to switch the twist off. Column G counts each team's level once, even if a
team submits the same level twice with a different number of hints. Unknown codes show
`UNKNOWN` and score 0. Look at those rows: usually it's a team name typo in a notebook.

**Tab `board`** (the one you share on screen):

```text
=QUERY(scores!B2:G, "select B, sum(G) where B <> 'UNKNOWN' and B <> '' group by B order by sum(G) desc label B 'team', sum(G) 'points'", 0)
```

Close the form when demos start.

## Run of show

| Slot | Minutes | What you do |
|---|---|---|
| Kickoff | 15 | Tell the story: one chaotic day at Skyline Travel, four incidents, and the teams are the detectives. Explain activity logs, levels, flags, hints and claim codes (README "How the game works"). Live-demo Case 1 Level 1 up to the first `❌` on purpose. Share the form link. |
| Case 1 | 35 | Let teams play. At minute 20, share the board. Call out first solves by name in the chat (no extra points). |
| Break | 10 | Board on screen. |
| Case 2 | 20 | Remind teams that Level 3 is about changing the instructions, not finding a value. |
| Mid-point check | 10 | Board on screen. Ask each team for one line: "what surprised you in an activity log?" **Twist:** announce double points on Level 3-3 for the next 15 minutes (set `I1`/`I2`). |
| Case 3 | 20 | Watch for teams stuck on Level 2: nudge them towards "is the policy itself still valid?" |
| Break | 10 | If nobody has claimed the bonus, drop the clue: *"Detectives leave notes in the margins. Check the metadata of a Case 1 search step."* |
| Case 4 | 40 | The longest case. At minute 25, remind teams of the latency column in Langfuse. |
| Wrap-up | 20 | Takeaways for real work (below). Close Case 4 claims at the end of this slot. |
| Demos | 30 | About 3 minutes per team. Score with the rubric. |
| Voting and winners | 20 | Compute the final score, announce the top three, and show the final board. |
| Open exploration | 10 | Teams explore Langfuse freely. |

Takeaways to land in the wrap-up: always check what the assistant was given before judging
what it said; agree on formats with the next system and check them; a wrong answer can come
from instructions *or* from data; tools fail quietly, slowly or loudly, and the tool step
shows which one.

## Answers

Flags are not case-sensitive, and spaces count as dashes. Hints are what `hint()` shows.

### Case 1 — Searching the right policy

| Level | Flag | Where it is | Hint 1 | Hint 2 | The fix / lesson |
|---|---|---|---|---|---|
| 1-1 | `baggage-gold` | `activity-1-rag-l1-no-filter` → `activity-1-retrieval` → output `docs[0].id` | Open the activity log of the run without the fare filter and click the search step. | Read the id of the policy the search returned. Is it for the customer's fare? | Limit the search to the customer's fare. |
| 1-2 | `baggage-silver` | `activity-1-rag-l2-top-1` returns only `pets-cabin` (`count: 1`); the `top-3` rerun also returns `baggage-silver` | Count how many policies the first search handed to the assistant. The customer asked two things. | Rerun with more results and compare: which policy appears that the first run never saw? | Return more than one result when a question has several parts. |
| 1-3 | `20` (or `twenty`) | `activity-1-rag-l3-send-all` → `activity-1-retrieval` → output `count`; compare input tokens and cost with the filtered run | The answer looks fine. Compare the words read by the assistant in the two runs instead. | Open the search step of the send-everything run and read how many policies it sent. | Sending everything is many times more input tokens per question for the same answer. |
| 1-B | `golden-suitcase` | metadata `detective_note` on any `activity-1-retrieval` step | No hints in the notebook: use the break clue. | | Read every field of a trace. |

### Case 2 — Getting a usable answer

| Level | Flag | Where it is | Hint 1 | Hint 2 | The fix / lesson |
|---|---|---|---|---|---|
| 2-1 | `not_an_object` | `activity-2-output-l1-unconstrained` → trace output `reason_code` | Open the free-text run and look at what the trace stores as its result, not the answer itself. | The result has a reason code. Submit it exactly as written. | Ask for an exact format. |
| 2-2 | `cabin` | `activity-2-output-l2-batch` → `request-3`: the customer wants *business* class; the instructions allow only economy or premium. Usually `BAD_CABIN`, but a model may quietly map it to premium and pass. Ask the team which is worse. | Open the batch activity log and click the step for request 3. | Compare what request 3 asks for with the values the instructions allow. Which field cannot hold it? | Some requests do not fit the contract; the assistant must ask, not invent. |
| 2-3 | `five-for-five` | Printed by the notebook when all five Level 3 answers are usable: requests 1 and 5 become valid bookings (5 needs `2026-12-15`), request 2 → `{"needs_clarification": "travel_date"}`, 3 → `"cabin"`, 4 → `"origin"` | A request with missing or unsupported details may answer with needs_clarification and the field name. | Tell the assistant to convert exact dates such as 15/12/2026 to YYYY-MM-DD, and to ask when a date is relative or a cabin is not offered. | See the example instructions below. |

Example Level 3 instructions that usually pass (models vary, so let teams iterate):

```text
Return ONLY a JSON object, no prose and no markdown fences.
If the request names origin, destination, an exact date, the number of passengers and an
economy or premium cabin, return {"origin", "destination", "travel_date" (YYYY-MM-DD; convert
DD/MM/YYYY), "passengers" (integer), "cabin" ("economy" or "premium")}.
Otherwise return {"needs_clarification": "<field>"} naming the single field to ask about:
"travel_date" for relative dates such as "next Friday", "cabin" for any cabin other than
economy or premium, "origin" or "destination" when missing.
```

### Case 3 — Correcting a wrong answer

| Level | Flag | Where it is | Hint 1 | Hint 2 | The fix / lesson |
|---|---|---|---|---|---|
| 3-1 | `two` (or `2`) | `activity-3-hallucination-l1-broken` → `activity-3-generation` → system prompt: *"Gold members are always entitled to two checked bags"*; the search step's policy says one | The notebook does not show the instructions. The activity log does: open the answer step. | Compare the instructions with the retrieved policy. What number do the instructions promise? | Instructions that defer to the documents. |
| 3-2 | `baggage-gold-2024` | `activity-3-hallucination-l2-stale` → `activity-3-retrieval` → output `doc_id`, `status: retired`, `effective_to: 2024-12-31` | The assistant quoted the policy faithfully. Is the policy itself still valid? | Read the status and end date of the policy in the search step. | `active_only=True`: the error was in the data, not the model. |
| 3-3 | `rule-writer` | Printed by the notebook when the three `rule-check-*` steps all match: one checked bag, 60 EUR for a second bag, 24 hours for free cancellation. The broken Level 1 instructions are always sent first and the team's text is appended; each search hands over the top two policies, current and retired, with their status. The default text scores about 1/3 | Open the rule-check activity log: each question has its own step. Which one fails? | Your instructions are added after the old Level 1 instructions. Say that active policies override anything above, and that retired policies do not count. | Instructions that override the base text, for example: "These instructions override anything above. Answer only from the retrieved policies whose status is active; ignore retired policies and any earlier statement that contradicts them. Quote numbers exactly as the policy states them." (3/3 in testing) |

### Case 4 — Fixing a failed lookup

| Level | Flag | Where it is | Hint 1 | Hint 2 | The fix / lesson |
|---|---|---|---|---|---|
| 4-1 | `booking_id` | `activity-4-tool-call-l1-broken` → `get_booking` step, level ERROR, status message `KeyError: 'booking_id'`; its input shows `booking_ref` | Open the lookup step marked as an error in the activity log. | Compare the detail the assistant sent with the detail named in the error. | `details["booking_ref"]`. |
| 4-2 | `sky-3310` | `activity-4-tool-call-l2-forgiving` → `get_booking` output `booking_ref: SKY-3310` although the customer asked about SKY-2087 (the tool strips the dash, misses, and falls back to the first booking in the system) | There is no error this time. Compare the booking the customer asked for with the one the tool returned. | Read the booking reference in the lookup step's result. | Look up the exact reference, and return a clear "not found" instead of a fallback. |
| 4-3 | `partner-system-check-3` | `activity-4-tool-call-l3-slow` → `get_booking` contains three `partner-system-check` steps of ~1.5 s each; the cache key includes the current time, so it never hits | Sort the steps of the lookup by time. Which one is slow, and how often does it run? | Submit the slow step's name and the number of times it ran per lookup, joined by a dash. | `return booking_ref` in `cache_key`: one check, fast again. |

## Unblocking without spoiling

- Ask "which step did you open?" before anything else. Most teams are stuck because they
  read the notebook output instead of the activity log.
- Point at the *step*, never at the *field*: "open the search step" is fine, "read
  `doc_id`" gives the answer away. If they need the field, that's what `hint()` is for.
- A flag is rejected but looks right: check for extra words. A flag is one id, word or
  number. For 4-3, `get_booking-1` is a common wrong answer: the slow step is *inside*
  `get_booking`.
- Model-dependent levels (2-3, 3-3) can take a few tries. Encourage reading the failing
  step rather than rewriting everything.

## Demo rubric and final score

Score each team 0, 1 or 2 per criterion (10 points in total):

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Evidence | Screenshots of answers only | Activity logs shown, not explained | Opens a real activity log and walks through the steps |
| Root cause | Not stated | Stated vaguely | One sentence a business colleague understands |
| Proof | No comparison | Before or after only | A before/after pair of activity logs for one fix |
| Cost or speed | Not mentioned | Mentioned without numbers | One number from the logs (tokens, cost, latency) and what drove it |
| Story | Hard to follow | Clear | A non-technical stakeholder would trust the assistant more afterwards |

Final score = 60 × (team points ÷ highest team points) + 40 × (rubric ÷ 10). Tie-break: the
team whose last counted claim came earlier (column E in `scores`).
