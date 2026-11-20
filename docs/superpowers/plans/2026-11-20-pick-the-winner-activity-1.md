# Pick the Winner — Activity 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship step 1 of the spec: regrouped corpus, a self-contained Gus story, the shared duel runner and check, core/bonus `report()`, duels 1.4–1.8, and notebook 1 rewritten in plain goofy English.

**Architecture:** A `DUELS` table in `experiment_utils.py` describes each Pick the Winner mission (activity, winner letter, message, per-option overrides, texts). `run_duel(mission)` runs both options through the activity's pipeline (`_rag_trace` for Activity 1) in one session; `_check_duel(mission)` decides from where comments sit on the two traces' top nodes. Later activities add their own pipeline to `DUEL_RUNNERS` and rows to `DUELS`.

**Tech Stack:** Python 3.12, Langfuse Python SDK 5.2 (server 4.80, self-hosted via compose), `langfuse.openai`, Jupyter/nbconvert.

**Spec:** `docs/superpowers/specs/2026-11-20-pick-the-winner-design.md`

## Global Constraints

- Files touched by this plan: `data/travel_corpus.json`, `experiment_utils.py`, `notebook-1-rag.ipynb` only (AGENTS.md: at most 3 files per change). README, MENTORS, AGENTS come in step 5 of the spec.
- A run prints one status line and one 📎 link, nothing else. Notebooks ship with cleared outputs. No cell raises.
- Checks rely only on observation names, where a comment sits, and facts the run code records. Never on comment text, model wording or token counts.
- Trace and option names never reveal the winner: `activity-1-duel-<mission>-option-a|b`.
- Duels never read the team's `production` prompt or its config.
- No item, character or animal from Activities 2–4 in Activity 1's data, traces or notebook (the `SKYE_IS_BACK` banner is the one exception).
- Participant text: short sentences, everyday words, goofy but friendly; no "monolith", "Rosetta stone", "Monolith reflex", "colleague"; no rare words ("HOLY MOLY!", not "HOLY MACKEREL!").
- Gus Haddock: names every fish (the lost bag holds Big Bertha), turns everything into a fishing story, yells "HOLY MOLY!", slips into Norwegian when excited.
- User messages carrying retrieved context use `## Customer message` and `## Lost-and-found entries (search results)` headings.
- There is no test suite. "Tests" here are scratch scripts in the scratchpad (never committed) that import `experiment_utils` against the running stack. Start it with `./start.sh` (= `docker compose up -d --build`) and source `.env` on the host.

## Review Focus

1. **A team reruns a duel after commenting** — the comment sits on the older session; the check must still be ✅ (any session counts). Test: Task 3 step 1, scenario "rerun after win".
2. **A comment on a step inside a duel trace** (e.g. on `activity-1-generation`) — must be ❌ with the "use the top line" nudge, not ✅. Test: Task 3 step 1, scenario "step comment".
3. **The team's edited `skye-lost-and-found` (any `flight_filter`/`top_k`, even a broken config)** — duels must run unaffected. Test: Task 4 step 4 runs every duel while `production` has `top_k: 1`.
4. **`check("1.5")` before `run_duel("1.5")` was ever run** — ❌ "No activity log yet", no exception. Test: Task 3 step 1, scenario "never run".
5. **Small `max_tokens` on a reasoning-style model returns empty output** instead of a cut sentence — 1.6's gap would vanish. Test: Task 4 step 4 asserts the loser's output is non-empty and shorter than the winner's.

---

### Task 1: Regroup the corpus and make Activity 1's data self-contained

**Files:**
- Modify: `data/travel_corpus.json`
- Modify: `experiment_utils.py:52-56` (corpus readers), `:303` (`search_log`), `:410` (`run_send_all`), `:561` (`search_notices`), `:429` (`_check_1_2`), mission 1.2 texts

**Interfaces:**
- Produces: `CORPUS["activity_1"]["lost_and_found"]`, `CORPUS["activity_2"]["requests"]`, `CORPUS["activity_3"]["notices"]`, `CORPUS["activity_3"]["instructions"]`, `CORPUS["activity_4"]["bookings"]`. Module names `BOOKINGS`, `REQUESTS`, `INSTRUCTIONS` keep their meaning. New constant `LOST_AND_FOUND = CORPUS["activity_1"]["lost_and_found"]`; `search_log` and the whole-log run read it.

- [ ] **Step 1: Write the failing check** — scratch `verify_t1.py`:

```python
import experiment_utils as eu
log = eu.LOST_AND_FOUND
ids = [e["id"] for e in log]
for gone in ("lf-rooster-sk205", "lf-ringlight-sk612", "lf-trombone-sk330", "lf-bagpipes-sk503", "lf-telescope-sk412"):
    assert gone not in ids, gone
assert eu.search_log(eu.LOG_QUERY, None, top_k=1)[0]["id"] == "lf-dolphin-sk205"
assert [e["id"] for e in eu.search_log(eu.LOG_QUERY, "SK101", top_k=1)] == ["lf-fish-bag-sk101"]
top3 = {e["id"] for e in eu.search_log(eu.LOG_QUERY, "SK101", top_k=3)}
assert {"lf-fish-bag-sk101", "lf-fishing-hat-sk101"} <= top3 and "lf-ice-sk101" not in top3
assert {e["id"] for e in eu.search_log("fish ice fresh warm", "SK101", top_k=2)} == {"lf-fish-bag-sk101", "lf-ice-sk101"}
print("T1 OK")
```

- [ ] **Step 2: Run it** — `set -a; . ./.env; set +a; LANGFUSE_BASE_URL=http://localhost:3000 .venv/bin/python <scratch>/verify_t1.py` → FAIL (`AttributeError: LOST_AND_FOUND`).

- [ ] **Step 3: Regroup `data/travel_corpus.json`** into `{"activity_1": {"lost_and_found": [...]}, "activity_2": {"requests": [...]}, "activity_3": {"notices": [...], "instructions": {...}}, "activity_4": {"bookings": {...}}}`. Move Activity 2–4 entries untouched. In Activity 1's log: delete the five ids above; insert, where the rooster was, `{"id": "lf-dolphin-sk205", "flight": "SK205", "item": "live dolphin", "text": "Found on board flight SK205, row 12: a big bag of water holding one live dolphin named Finnegan. He splashes everyone who walks past."}`; insert right after `lf-fishing-hat-sk101` `{"id": "lf-ice-sk101", "flight": "SK101", "item": "melted ice", "text": "SK101 fish cooler: the ice melted at 09:00. The fish are warm and a bit sad."}`. The ice text must contain none of the substrings `bag`, `found`, `on`, `board` (the keyword search is substring-based), so it scores 0 for `LOG_QUERY` and sorts after the hat.

- [ ] **Step 4: Update the readers** in `experiment_utils.py` to the new paths; `_check_1_2` uses `lf-dolphin-sk205`; mission 1.2 title "Who invited the dolphin?", nudges and solved text say dolphin (e.g. solved: "Finnegan is back on flight SK205. He splashed the pilot on the way."). `grep -n rooster experiment_utils.py` must then only hit Activity 3 code and `SKYE_IS_BACK`.

- [ ] **Step 5: Run step 2 again** → `T1 OK`. Then execute all four notebooks headlessly (AGENTS.md command, host form) → all finish without error.

- [ ] **Step 6: Commit** — `git add data/travel_corpus.json experiment_utils.py && git commit -m "refactor: group the corpus by activity; a dolphin replaces the rooster in Gus's log"`

---

### Task 2: Gus's new voice, delimited message, and 1.1 on the whole trace

**Files:**
- Modify: `experiment_utils.py` — `CUSTOMER_MESSAGE`, `_rag_trace`, `_check_1_1`, mission 1.1/1.2/1.3 texts

**Interfaces:**
- Produces: `_rag_trace(trace_name, prompt, items, search_input, session_id, *, message=CUSTOMER_MESSAGE, system=None, max_tokens=800, slow_seconds=0, search=True, extra_facts=None) -> str` (trace id). `prompt` may be `None` when `system` is given (no prompt link). `search=False` skips the `activity-1-retrieval` step and the entries section. `slow_seconds > 0` adds a span `double-check-with-desk` that sleeps that long, with output `{"desk": "still checking..."}`. Records facts `flight_filter`, `top_k`, `item_ids`, `search`, `max_tokens`, `slow_seconds`, plus `extra_facts`.

- [ ] **Step 1: Write the failing check** — scratch `verify_t2.py`: call `eu.run_rag()`, flush, fetch the newest `activity-1-generation` observation of `eu.LAST_RUN["activity-1-rag"]` and assert its input's user message starts with `"## Customer message\n"` and contains `"\n\n## Lost-and-found entries (search results)\n- "`; assert `eu._check_1_1()[0] is False`; then create a comment on that trace's root observation through `eu.langfuse.api.comments.create(...)` (project id from `eu.langfuse.api.projects.get().data[0].id`, `object_type="OBSERVATION"`) and assert `eu._check_1_1()[0] is True`.

- [ ] **Step 2: Run it** → FAIL on the message heading.

- [ ] **Step 3: Implement.** User content is `f"## Customer message\n{message}\n\n## Lost-and-found entries (search results)\n{entries}"`, or `f"## Customer message\n{message}"` when `search=False`. New `CUSTOMER_MESSAGE` in Gus's voice, keeping flight SK101, the bag of fish and the lucky fishing hat (e.g. "HOLY MOLY! Gus here, flight SK101. Did anyone find my bag of fish? Big Bertha is in there! And my lucky fishing hat?! I caught Big Bertha wearing that hat."). `_check_1_1` → `has_comment("activity-1-rag", None)`, nudge: "Click the top line of the tree (activity-1-rag) and leave any comment there." 1.1 title "Say hi to the trace". Rewrite 1.1–1.3 nudges/solved texts to the language rules.

- [ ] **Step 4: Run step 2 again** → PASS; also rerun `verify_t1.py` → `T1 OK`.

- [ ] **Step 5: Commit** — `git commit -am "feat: Gus speaks up, the model's input has headings, 1.1 comments on the whole trace"`

---

### Task 3: Duel runner, duel check, core/bonus report, and 1.4 as the first duel

**Files:**
- Modify: `experiment_utils.py` — `has_comment` (extract helper), `report`, `seed_prompts`, Activity 1 run/check section (delete `run_send_all`, `_check_1_4`)
- Modify: `notebook-1-rag.ipynb` — cell `c02` import (`run_duel` replaces `run_send_all`), cell `c16` → `run_duel("1.4")` (minimal; full rewrite is Task 5)

**Interfaces:**
- Consumes: `_rag_trace` (Task 2).
- Produces:
  - `DUELS: dict[str, dict]`, row keys: `activity:int`, `title:str`, `winner:"a"|"b"`, `status:str` (the printed line, must not hint at the winner), `options:{"a":dict,"b":dict}` (kwargs for the activity runner), `prompts:{"a":str,"b":str}|None` (seeded `duel-<mission>` texts), `hint:str` (shown when only the loser is commented), `solved:str`.
  - `DUEL_RUNNERS: dict[int, Callable[[str, str, dict, str], str]]` — `(mission, option, overrides, session_id) -> trace_id`; Activity 1's is `_gus_duel`.
  - `run_duel(mission:str) -> None` (wrapped in `_safe_run`; unknown mission prints one ❓ line).
  - `session_url(trace_id:str, session_id:str) -> str` — `trace_url(trace_id)` with `/traces/<id>` replaced by `/sessions/<session_id>`.
  - `_commented(trace_id:str, root_id:str, step_name:str|None) -> bool` — the per-root body of `has_comment`; `has_comment` loops over it.
  - `_duel_outcome(sessions:list[dict]) -> str` — each dict `{"winner":bool, "loser":bool, "step":bool}`; returns `"won"` if any session has winner and not loser, else `"loser"` if any has loser and not winner, else `"both"` if any has both, else `"step"` if any has a step comment, else `"none"`.
  - `_check_duel(mission) -> (bool, str)`; `MISSIONS[mission]` rows for duels carry `"bonus": True`.
  - `report(activity=None)`: runs core missions, prints `🏁 <done> of <n> missions done.`, then `🥊 Pick the winner (bonus)` followed by each duel check and `🥊 <won> of <m> duels won.`; `SKYE_IS_BACK` when `activity is None` and all core missions pass.

- [ ] **Step 1: Write the failing checks** — scratch `verify_t3.py`:

```python
import experiment_utils as eu
O = eu._duel_outcome
assert O([]) == "none"
assert O([{"winner": True, "loser": False, "step": False}]) == "won"
assert O([{"winner": False, "loser": True, "step": False}]) == "loser"
assert O([{"winner": True, "loser": True, "step": False}]) == "both"
assert O([{"winner": False, "loser": False, "step": True}]) == "step"
assert O([{"winner": True, "loser": True, "step": False}, {"winner": True, "loser": False, "step": False}]) == "won"   # rerun after win
assert O([{"winner": False, "loser": True, "step": False}, {"winner": True, "loser": False, "step": False}]) == "won"
assert eu.MISSIONS["1.4"]["bonus"] is True and not eu.MISSIONS["1.2"].get("bonus")
# live: never run → check prints "No activity log yet" and returns False (use a mission id with no traces yet, e.g. after Task 4 "1.8" on a fresh stack; here, temporarily, "1.4" before running it)
eu.run_duel("1.4")
sid = ...  # session id from the facts of the newest activity-1-duel-1.4-option-a root
assert eu.check("1.4") is False
# comment on loser's root → False; on a step inside the winner → False; on winner root → True
print("T3 OK")
```

- [ ] **Step 2: Run it** → FAIL (`_duel_outcome` missing).

- [ ] **Step 3: Implement** as in the Interfaces. Details the signatures do not settle:
  - Session id `f"activity-{n}-duel-{mission}-{RUN_ID}-{uuid.uuid4().hex[:4]}"`, tag `activity-{n}`; trace names `f"activity-{n}-duel-{mission}-option-{x}"`; facts on each root include `mission`, `option`, `session_id`.
  - `run_duel` runs option `a` then `b`, sets `LAST_RUN` for both trace names, prints `f"{status}  📎 Open the session: {session_url(...)}"`, flushes.
  - `_check_duel` reads roots of both names with `fields="core,basic,metadata"`, groups by `facts.session_id`, raises `_NoTrace` when neither name has roots or `LAST_RUN` ids are missing. `"step"` = a comment on `activity-1-retrieval` or `activity-1-generation` of either trace. Nudges: `"loser"` → row `hint`; `"both"` → "Skye can only ship one. Pick one run and comment only on it."; `"step"` → "That comment is on a step. Click the top line of the run you would ship."; `"none"` → "Open the session, compare the two runs, and comment on the top line of the one you would ship."
  - `seed_prompts` also creates, when `duel-<mission>` is missing, version 1 with labels `["option-a"]` and version 2 with `["option-b"]` from each row's `prompts`.
  - `_gus_duel`: loads `duel-<mission>` at label `option-<x>` when the row has `prompts`, else uses `system=GUS_DUEL_SYSTEM`; search defaults to `query=LOG_QUERY, flight=GUS_FLIGHT, top_k=3` unless overridden by `search="whole_log"` / `search=False` / `query=...`; calls `_rag_trace`.
  - `GUS_DUEL_SYSTEM` (fixed, defect-free): Skye answers Gus kindly and only from the entries; the lost-and-found desk is at Gate 12, next to the giant pretzel; from Gate 3: walk past the coffee shop, take the escalator down, turn left at the giant pretzel, the desk is on the right.
  - Row 1.4: title "Pick the winner: the whole log", winner `"a"`, options `a: {}`, `b: {"search": "whole_log"}`, hint "Show the Tokens and Cost columns in Tracing → Traces. Both runs found Big Bertha. Which one cost more?".

- [ ] **Step 4: Run step 2 again** → `T3 OK`; rerun `verify_t1.py`, `verify_t2.py`.

- [ ] **Step 5: Commit** — `git add experiment_utils.py notebook-1-rag.ipynb && git commit -m "feat: pick-the-winner duels, bonus report line, 1.4 as the first duel"`

---

### Task 4: Duels 1.5–1.8

**Files:**
- Modify: `experiment_utils.py` — `DUELS` rows, `MISSIONS` registration

**Interfaces:**
- Consumes: `DUELS` row shape, `_gus_duel`, `_rag_trace` kwargs (Tasks 2–3).

| Mission | Title | Winner | Message (Gus's voice) | a | b | Hint (loser only) |
|---|---|---|---|---|---|---|
| 1.5 | The desk closes in 10 minutes | b | desk closes in 10 minutes, where is it, he is "running! Well, walking fast." | `{"slow_seconds": 6}` | `{}` | "Open the Timeline of both runs. Gus has 10 minutes." |
| 1.6 | Directions to the desk | a | step-by-step route from Gate 3; "I once got lost on my own boat." | `{"max_tokens": 400}` | `{"max_tokens": 25}` | "Read the end of both answers. Did one stop in the middle?" |
| 1.7 | Is Big Bertha still fresh? | b | is Big Bertha still fresh, she has been in the bag since 6 a.m. | `{"search": False}` | `{"query": "fish ice fresh warm", "top_k": 2}` | "Does each run have a search step? What did it find?" |
| 1.8 | HOLY MOLY, in Norwegian | a | in Norwegian: "HOLY MOLY! Hei Skye! Har dere funnet fiskeposen min? Big Bertha er der inne!" | prompt option-a | prompt option-b | "Click the prompt version on each answer step and read it." |

Prompts: `duel-1.7` a = "You are Skye. Never say you don't know. Always sound 100% sure, even without facts.", b = "You are Skye. Answer only from the lost-and-found entries. If they don't say, say you don't know." `duel-1.8` a = defect-free Gus text + "Always answer in the customer's language.", b = same + "Always answer in English." Status lines all neutral, e.g. "🥊 Two Skyes answered Gus. Only one keeps the job."

- [ ] **Step 1: Write the failing check** — scratch `verify_t4.py`: for each of 1.5–1.8, three times: `run_duel(m)`, then read the two traces and assert the gap —
  - 1.5: loser root latency ≥ winner + 5 s.
  - 1.6: loser output non-empty and shorter than winner's; loser `finish_reason == "length"` if the generation records it.
  - 1.7: loser trace has no `activity-1-retrieval`; winner's retrieval output contains `lf-ice-sk101`; print both answers for a human glance.
  - 1.8: winner answer's prompt is `duel-1.8` with label option-a; print both answers (Norwegian vs English) for a human glance.
  Plus: with `skye-lost-and-found` production set to `top_k: 1`, every duel still runs (Review Focus 3). Plus `check(m)` False before any comment, True after a comment on the winner root.

- [ ] **Step 2: Run it** → FAIL (`No mission '1.5'`).

- [ ] **Step 3: Add the rows** and register them in `MISSIONS` with `bonus: True`, `check: lambda m=m: _check_duel(m)`.

- [ ] **Step 4: Run step 2 again** → all assertions pass three times in a row. If 1.6's loser comes back empty, raise 25 until it is a cut sentence; if 1.7's loser hedges ("I don't know"), strengthen option-a's text. Record final values.

- [ ] **Step 5: Commit** — `git commit -am "feat: duels 1.5-1.8 follow Gus through the airport"`

---

### Task 5: Rewrite notebook 1

**Files:**
- Modify: `notebook-1-rag.ipynb` (all Markdown cells; code cells per mission)

**Interfaces:**
- Consumes: `check`, `report`, `run_rag`, `run_duel` (Tasks 2–4).

Cell order: header (purpose, what to expect, bad practice, good practice, why it works, deliverable — rewritten), how to play (adds one line: "🥊 Pick the winner missions are bonus: compare two runs and comment on the one you'd ship"), import, then per mission: briefing with numbered **In Langfuse** steps → run cell → collapsed 💡 Stuck? → `check("<m>")`, for 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, then the 🏁 report cell `report(1)`. Duel briefings end with: "Click the **top line** of the run you would ship and leave a comment." Deliverable: core missions ✅ and one before/after pair (dolphin vs Big Bertha). Plain words for trace, step, generation, session, prompt version at first use. Briefings never name the winner.

- [ ] **Step 1: Write the failing check** — scratch `verify_t5.sh`:

```bash
f=notebook-1-rag.ipynb
! grep -qiE 'monolith|rosetta|colleague|rooster|crowsalot|coco|edna|piano|cockpit|ring light|mackerel' "$f" || { echo "banned word"; exit 1; }
for m in 1.1 1.2 1.3 1.4 1.5 1.6 1.7 1.8; do grep -q "check(\\\\\"$m\\\\\")" "$f" || { echo "missing $m"; exit 1; }; done
python3 -c "import json;nb=json.load(open('$f'));assert all(not c.get('outputs') for c in nb['cells'] if c['cell_type']=='code')"
echo T5 OK
```

- [ ] **Step 2: Run it** → FAIL (banned word / missing 1.5).

- [ ] **Step 3: Rewrite the notebook** to the cell order above (NotebookEdit or a JSON rewrite that keeps cell ids `c00…` for existing cells).

- [ ] **Step 4: Verify** — `verify_t5.sh` → `T5 OK`; headless execution of notebook 1 (AGENTS.md command) → finishes, every check prints ❌, no traceback; then clear outputs again (`jupyter nbconvert --clear-output --inplace notebook-1-rag.ipynb`) and rerun `verify_t5.sh`.

- [ ] **Step 5: Commit** — `git commit -am "docs: notebook 1 in plain goofy English with Gus's duels"`

---

### Task 6: Whole-activity verification

- [ ] **Step 1:** Fresh kernel, play Activity 1 end to end in the UI path the notebook describes (comments via the Langfuse UI for at least 1.1 and one duel, to confirm a UI comment counts) → `report(1)` shows core ✅ and the duel line.
- [ ] **Step 2:** Execute notebooks 2–4 headlessly → finish without error (the corpus regroup did not break them).
- [ ] **Step 3:** In Langfuse, grep-by-eye the Activity 1 traces' inputs: no rooster, ring light, piano, cockpit.
- [ ] **Step 4:** Report runtime edge cases to the user (missing keys, stale kernel, rate limits on 8 duel calls, flush, model availability, empty output at small `max_tokens`).

---

### Task 7: Language and storytelling pass on notebooks 2–4

Requested by the game master at the plan handoff: apply §5.2 (characters) and §5.6 (language rules) to the Markdown of notebooks 2–4 now. No mechanics change: same missions, run cells, checks, observation and prompt names. Their duels and data cleanups stay in spec steps 2–4.

**Files:**
- Modify: `notebook-2-output-format.ipynb`, `notebook-3-hallucination.ipynb`, `notebook-4-tool-calling.ipynb` (Markdown cells only)

- [ ] **Step 1: Write the failing check** — scratch `verify_t7.sh`: for each notebook, fail on `monolith|rosetta|colleague`; notebook 2 also on `fish|gus|rooster|piano|edna|barnaby`; notebook 3 on `fish|gus|coco|selfie|piano|edna`; notebook 4 on `fish|gus|coco|rooster|barnaby`; code cells byte-identical to `git show HEAD:<nb>`; no outputs.
- [ ] **Step 2: Run it** → FAIL (Rosetta blocks; 4.2 mentions a fisherman).
- [ ] **Step 3: Rewrite** each notebook's Markdown: header sections kept, in plain goofy English; Coco, Barnaby and Edna get the §5.2 personalities; 4.2's wrong result described without naming another story's item.
- [ ] **Step 4: Verify** — `verify_t7.sh` → OK; headless execution of notebooks 2–4 → finish without error; clear outputs.
- [ ] **Step 5: Commit** — `git commit -am "docs: notebooks 2-4 in plain goofy English, each story on its own"`
