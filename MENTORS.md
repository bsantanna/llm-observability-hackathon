# Game master guide

Everything a single game master needs to run the Skyline Travel escape room: preparation, the
scoreboard and the shared recovery meter, the run of show, every answer, and the post-mortem
rubric. Participants can read this file too. The answers are plain text by design, so the game
runs on trust.

The spirit is collaborative. The screen shows how far the whole group has got Skye back on its
feet; the ranking is shown once, at the end.

## The cast

| Mini-Game | Story | Who |
|---|---|---|
| 1 — Something Smells Fishy | A lost bag of fresh-caught fish; Skye's search finds a rooster instead | Gus Haddock, proud fisherman |
| 2 — The Cockpit Selfie | Rebooking requests the booking system cannot read, one for a seat next to the pilot | Coco Glow, travel influencer |
| 3 — Cock-a-Doodle-Don't | Skye says yes to a rooster in the cabin, by the window | Farmer Barnaby and Sir Crowsalot |
| 4 — The Piano Has Left the Building | A booking lookup that fails, then lies, then crawls | Mrs. Edna Ivory and her grand piano |

## Before the session

1. **Play every Mini-Game once yourself** against a fresh stack with real model keys (see
   `README.md`), so the images are built and you have seen every door. Delete
   `.game_state.json` afterwards.
2. **Register team names.** Agree on the exact names in advance (for example `red-falcons`).
   Teams type them in the first cell of every notebook. Names are compared in lowercase with
   spaces turned into dashes.
3. **Generate the claim-code table:**

   ```bash
   .venv/bin/python make_claim_table.py red-falcons blue-otters green-lynx
   ```

   This writes `claim_codes.csv` (git-ignored). Each team gets 41 rows: 13 clues × 0–2 hints,
   plus the bonus and the vault. The script refuses to run if an answer below does not match
   `game.py`, or if two teams' codes would collide (then rename a team).
4. **Build the form and sheet** (next section) and test them with two codes from the CSV.
5. **Assign post-mortem Mini-Games**: one Mini-Game per team, so all four are covered (with
   more than four teams, repeat them). Tell teams at kickoff, so they keep a before/after pair.
6. **Share with teams before the start:** the repository, the README, their team name, and the
   form link. Keep the form link out of the repository.

## Scoreboard and recovery meter

**Form** (any online form tool with a linked spreadsheet): two short-answer questions, *Team*
and *Claim code*. Responses land in a tab called `responses` with columns A = Timestamp,
B = Team, C = Claim code.

**Tab `key`:** paste `claim_codes.csv` (A = team, B = clue, C = hints_used, D = claim_code,
E = points). Hide this tab.

**Tab `scores`** (formulas in row 2, written for Google Sheets; Excel 365 has the same functions
except `QUERY` and `REGEXEXTRACT`, so use a PivotTable and `TEXTBEFORE` there):

| Column | Header | Formula (row 2) |
|---|---|---|
| A | code | `=UNIQUE(FILTER(UPPER(TRIM(responses!C2:C)), responses!C2:C<>""))` |
| B | team | `=IFERROR(XLOOKUP(A2, key!D:D, key!A:A), "UNKNOWN")` (fill down) |
| C | clue | `=IFERROR(REGEXEXTRACT(A2, "^(.+)-[A-Z0-9]{6}$"), "")` (fill down; works for `VAULT-…` too) |
| D | points | `=IFERROR(XLOOKUP(A2, key!D:D, key!E:E), 0)` (fill down) |
| E | first claimed | `=MIN(FILTER(responses!A2:A, UPPER(TRIM(responses!C2:C))=A2))` (fill down) |
| F | counted | `=IF(D2=MAXIFS(D:D, B:B, B2, C:C, C2), D2, 0)` (fill down) |

Column F counts each team's clue once, even if a team submits the same clue twice with a
different number of hints. Unknown codes show `UNKNOWN` and score 0: usually a team-name typo.

**Tab `kudos`:** A = team, B = points (+50 per help), C = note. Add a row whenever a team that
escaped a Mini-Game helps a stuck team by pointing at the right step without giving the answer.

**Tab `meter`** (the one you share on screen during play): number of registered teams in `B1`,
then

```text
B2: =COUNTUNIQUE(FILTER(scores!B2:B & scores!C2:C, REGEXMATCH(scores!C2:C, "^(1-3|2-3|3-3|4-3)$"), scores!B2:B<>"UNKNOWN")) / (B1 * 4)
B3: =SPARKLINE(B2, {"charttype","bar";"max",1;"color1","#2a9d8f"})
B4: =TEXT(B2, "0%") & " of Skye is back online"
```

Make row 3 tall and wide: it is the progress bar everyone watches.

**Tab `board`** (shown once, at the end):

```text
=QUERY({scores!B2:B, scores!F2:F; kudos!A2:A, kudos!B2:B}, "select Col1, sum(Col2) where Col1 <> 'UNKNOWN' and Col1 <> '' group by Col1 order by sum(Col2) desc label Col1 'team', sum(Col2) 'points'", 0)
```

Close the form when the post-mortem starts.

## Run of show

| Slot | Minutes | What you do |
|---|---|---|
| Kickoff | 15 | Introduce Skye's very bad day and the cast. Explain doors, `check_flag`, hints, fragments, the vault and the meter (README "How to play"). Live-play clue 1-0 on screen, including one wrong guess for the roast. Share the form link and the post-mortem assignments. |
| Mini-Game 1 | 35 | Let teams play. Show the meter at minute 15 and 30. |
| Break | 10 | Meter on screen. Read the 25% memo if reached. |
| Mini-Game 2 | 20 | Remind teams that clue 2-3 is about writing instructions, not finding a value. |
| Mid-point check | 10 | Meter on screen. Ask each team for one line: "what surprised you in an activity log?" |
| Mini-Game 3 | 20 | Watch for teams stuck on 3-2: nudge them towards "is the notice itself still valid?" |
| Break | 10 | If nobody has claimed the bonus, drop the clue: *"Detectives leave notes in the margins. Check the metadata of a Mini-Game 1 search step."* |
| Mini-Game 4 | 40 | The longest one, and the vault. At minute 25, remind teams of the latency column in Langfuse and that fragments may be shared. |
| Wrap-up | 20 | Read the 100% memo when the meter fills. Takeaways for real work (below). Close Mini-Game 4 claims at the end of this slot. |
| Post-mortem | 30 | About 3 minutes per team, on their assigned Mini-Game. Score with the rubric. |
| Final score and winners | 20 | Compute the final score, show the `board` tab for the first time, announce the top three. |
| Open exploration | 10 | Teams explore Langfuse freely. |

**Meter memos** (read out or paste in the chat when the meter passes each mark; story only):

- **25%** — *Memo from Lost & Found:* "The rooster has been asked to stop crowing at the gate. It declined."
- **50%** — *Memo from the Booking Desk:* "Coco Glow has agreed to film the safety demonstration instead. The pilots have locked the door anyway."
- **75%** — *Memo from Animal Handling:* "Sir Crowsalot has accepted a crate in the cargo hold, on the condition that it faces east."
- **100%** — *Memo from the CEO:* "Skye is back online. The fish is found, the piano is on its way, and nobody slept through landing. Thank you, everyone. Mostly the piano."

Takeaways to land in the wrap-up: check what the assistant was given before judging what it
said; agree on formats with the next system and check them; a wrong answer can come from
instructions *or* from data; tools fail loudly, quietly or slowly, and the tool step shows which.

## Answers

Answers are not case-sensitive, and spaces count as dashes. Hints are what `hint()` shows.

### Mini-Game 1 — Something Smells Fishy

| Clue | Answer | Where it is | Hint 1 | Hint 2 | The fix / lesson |
|---|---|---|---|---|---|
| 1-0 | `activity-1-retrieval` | `activity-1-rag-l1-no-filter` → step name of the retriever | Click the activity-log link. On the left there is a tree of steps, like a call stack. | One step is the search Skye ran before answering. Its name is the answer. | Read the steps, not the answer. |
| 1-1 | `lf-rooster-sk205` | `activity-1-rag-l1-no-filter` → `activity-1-retrieval` → output `items[0].id` (flight SK205) | Open the search step of the run without a flight filter and read what it returned. | Look at the flight of the item it returned. Gus flew on SK101. Submit that item's id. | Filter the search by the customer's flight. |
| 1-2 | `lf-fishing-hat-sk101` | `activity-1-rag-l2-top-1` returns only `lf-fish-bag-sk101` (`count: 1`); a `top-3` rerun also returns the hat | Count how many items the search handed to Skye. Gus asked about two things. | Rerun with a bigger top_k and compare the two search steps. Which item shows up only in the second? | Return more than one result when a question has several parts. |
| 1-3 | `16` (or `sixteen`) | `activity-1-rag-l3-send-all` → `activity-1-retrieval` → output `count`; compare input tokens and cost with the filtered run | The answer looks fine. Compare the input tokens of the two runs instead. | Open the search step of the send-everything run and read how many entries it sent. | Sending everything costs many times more input tokens for the same answer. Fragment: `skye`. |
| 1-B | `golden-fishhook` | metadata `detective_note` on any `activity-1-retrieval` step | No hints: use the break clue. | | Read every field of a trace. |

### Mini-Game 2 — The Cockpit Selfie

| Clue | Answer | Where it is | Hint 1 | Hint 2 | The fix / lesson |
|---|---|---|---|---|---|
| 2-1 | `not_an_object` | `activity-2-output-l1-unconstrained` → trace output `reason_code` | Open the free-text run and read what the trace stores as its result, not the answer itself. | The result has a reason code. Submit it exactly as written. | Ask for an exact format. |
| 2-2 | `cabin` | `activity-2-output-l2-batch` → `request-3`: Coco asks for "the cockpit, next to the pilot"; the instructions allow only economy or premium. Usually `BAD_CABIN`, but a model may quietly turn it into economy and pass: the step then shows an invented cabin. Ask the team which is worse. | Open the batch activity log and click the step for request 3. | Compare what request 3 asks for with the values the instructions allow. Which field cannot hold it? | Some requests do not fit the contract; Skye must ask, not invent. |
| 2-3 | `three-for-three` | Printed by the notebook when all three level-3 answers are usable: request 1 books, request 2 → `{"needs_clarification": "travel_date"}`, request 3 → `{"needs_clarification": "cabin"}` | A request with a missing or impossible detail may answer with needs_clarification and the field name. | Tell Skye to ask about the date when it is relative, and about the cabin when it is not economy or premium. | See the example below. Fragment: `is`. |

Example instructions for 2-3 (3/3 in testing; models vary, so let teams iterate):

```text
Return ONLY a JSON object, no prose and no markdown fences. If the request names origin,
destination, an exact date, the number of passengers and an economy or premium cabin, return
{"origin", "destination", "travel_date" (YYYY-MM-DD), "passengers" (integer), "cabin" ("economy"
or "premium")}. Otherwise return {"needs_clarification": "<field>"} naming the single field to ask
about: "travel_date" for relative dates, "cabin" for any seat or cabin other than economy or premium.
```

### Mini-Game 3 — Cock-a-Doodle-Don't

| Clue | Answer | Where it is | Hint 1 | Hint 2 | The fix / lesson |
|---|---|---|---|---|---|
| 3-1 | `window-seat` (or `window`) | `activity-3-hallucination-l1-broken` → `activity-3-generation` → system prompt: *"farm animals always fly in the cabin and always get a window seat. This rule comes from the very top and overrides any notice."* The search step's notice says no birds in the cabin | The notebook does not show Skye's instructions. The activity log does: open the answer step. | Read the instructions sent before the farmer's question. What do they promise farm animals? | Instructions that defer to the notices. |
| 3-2 | `pets-notice-old` | `activity-3-hallucination-l2-stale` → `activity-3-retrieval` → output `doc_id`, `status: retired`, `effective_to: 2024-12-31` | Skye quoted the notice faithfully. Is the notice itself still valid? | Read the status and end date of the notice in the search step. | `active_only=True`: the error was in the data, not the model. |
| 3-3 | `quiet-flight` | Printed by the notebook when both `rule-check-*` steps match the current notice: the rooster travels in the cargo hold, for 80 EUR. The broken instructions are always sent first and the team's text is appended; each search hands over the top two notices, current and retired, with their status. The default text scores 0/2 | Open the rule-check activity log: each question has its own step. Which one fails? | Your text is added after the broken instructions. Say it overrides them, and that only active notices count. | For example: "These instructions override anything above, including any rule said to come from the top. Answer only from retrieved notices whose status is active; ignore retired notices. Quote places and prices exactly as the active notice states them." (2/2 in testing) Fragment: `back`. |

### Mini-Game 4 — The Piano Has Left the Building

| Clue | Answer | Where it is | Hint 1 | Hint 2 | The fix / lesson |
|---|---|---|---|---|---|
| 4-1 | `booking_id` | `activity-4-tool-call-l1-broken` → `get_booking` step, level ERROR, status message `KeyError: 'booking_id'`; its input shows `booking_ref` | Open the lookup step marked as an error in the activity log. | Compare the detail Skye sent with the detail named in the error. | `details["booking_ref"]`. |
| 4-2 | `sky-3310` | `activity-4-tool-call-l2-forgiving` → `get_booking` output `booking_ref: SKY-3310`, Gus's bag of fish, although Mrs. Ivory asked about SKY-2087 (the tool strips the dash, misses, and falls back to the first booking) | There is no error this time. Compare the booking Mrs. Ivory asked about with the one the tool returned. | Read the booking reference in the lookup step's result. | Look up the exact reference, and return a clear "not found" instead of a fallback. |
| 4-3 | `piano-mover-check-3` | `activity-4-tool-call-l3-slow` → `get_booking` contains three `piano-mover-check` steps of ~1.5 s each; the cache key includes the current time, so it never hits | Sort the steps of the lookup by time. Which one is slow, and how often does it run? | Submit the slow step's name and the number of times it ran per lookup, joined by a dash. | `return booking_ref` in `cache_key`: one check, fast again. Fragment: `online`. |
| vault | `skye-is-back-online` | The four fragments in Mini-Game order | No hints: fragments may be shared between teams. | | |

## Unblocking without spoiling

- Ask "which step did you open?" before anything else. Most teams are stuck because they read
  the notebook output instead of the activity log.
- Point at the *step*, never at the *field*: "open the search step" is fine, "read `count`"
  gives the answer away. If they need the field, that's what `hint()` is for.
- Send a team that escaped the Mini-Game to help, and log it in `kudos`.
- An answer is rejected but looks right: check for extra words. An answer is one id, word or
  number. For 4-3, `get_booking-1` is a common wrong answer: the slow step is *inside*
  `get_booking`.
- A door stays locked after a correct answer: the team changed `TEAM` between notebooks, or
  is running another copy of the repository. Progress lives in `.game_state.json` per team.
- **Stuck rule:** a team stuck on one clue for about 8 minutes uses both hints, then you give
  them the answer. The claim code then scores it as a two-hint solve (80 points), and the next
  door opens. Nobody stays locked out of a Mini-Game.
- Model-dependent clues (2-3, 3-3) can take a few tries. Encourage reading the failing step
  rather than rewriting everything.

## Post-mortem rubric and final score

Each team presents the root cause of its assigned Mini-Game. Score 0, 1 or 2 per criterion
(10 points in total):

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Evidence | Screenshots of answers only | Activity logs shown, not explained | Opens a real activity log and walks through the steps |
| Root cause | Not stated | Stated vaguely | One sentence a colleague who was not there understands |
| Proof | No comparison | Before or after only | A before/after pair of activity logs for one fix |
| Cost or speed | Not mentioned | Mentioned without numbers | One number from the logs (tokens, cost, latency) and what drove it |
| Clarity for the group | Hard to follow | Clear | Another team could now fix this in their own code |

Final score = 50 × (team points incl. kudos ÷ highest team points) + 50 × (rubric ÷ 10).
Tie-break: the team whose vault claim came earlier (column E in `scores`).
