# Langfuse Missions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the escape-room mechanics with Langfuse missions: run cells print only a status line and a trace link, players act in the Langfuse UI (comment, score, edit prompts), and `check("<mission>")` verifies the action through the Langfuse API.

**Architecture:** `experiment_utils.py` seeds Skye's prompts (text + config) into the team's Langfuse at import, runs each activity's pipeline with the `production` prompt linked to the generation, records code-controlled **facts** on each trace, and exposes `check(mission)` / `report(activity)`, which read comments, scores and facts back from the Langfuse API. `game.py` and `make_claim_table.py` are deleted. Notebooks are tutorial Markdown plus run and check cells.

**Tech Stack:** Python 3.12, Jupyter, Langfuse server 4.80 (compose stack), Langfuse Python SDK 5.2 (`langfuse.openai`).

**Spec:** `docs/superpowers/specs/2026-11-20-langfuse-missions-design.md`

## Global Constraints

- Branch `langfuse-missions` (exists, spec committed). Pieces of at most 3 files per commit; the repository must be consistent at the end of the branch, not after every task.
- No test suite is added (AGENTS.md). Verification is scratch scripts in the session scratchpad run inside the stack (`docker compose exec jupyter python - <<'EOF'`) plus headless notebook execution; scratch scripts are never committed.
- Run cells print exactly one status line plus the trace link, e.g. `🛫 Skye answered Gus.  📎 Open the activity log: <url>`. Never Skye's answer, ids, item names, tokens, cost, latency, prompt text, reason codes or pass counts.
- No cell raises because a mission is not done, a prompt config is malformed, or a trace is not ingested yet. `check` and `report` never raise.
- No typed answers anywhere; no team name, claim code, points, fragments, vault, meter or `.game_state.json`.
- Checks rely only on code-controlled data (observation names, comment/score placement, facts recorded by code) and ignore comment text and model wording — except where the spec keeps a code-checked model output (2.2 validator, 3.2 rule questions).
- Trace names `activity-<n>-...`; one session per activity per kernel (`activity-<n>-{RUN_ID}`); flush at the end of each run function, so a check right after a run can see it.
- Prompts are seeded only when missing; never overwritten. Run functions fetch with `cache_ttl_seconds=0` and `label="production"`.
- Shipped notebooks: outputs cleared (`jupyter nbconvert --clear-output --inplace`).
- Copy: tone absurd and light; the joke is the situation, never the person; the bird is a "rooster"; no real person, employer, event, date or meeting platform; the assistant is "Skye" at fictional Skyline Travel.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

### Notebook mission template (used by Tasks 3–6)

Each mission is, in order:
1. Markdown: `## 🕵️ Mission <id> — <title>`, two or three story lines, one Rosetta-stone line, then **In Langfuse** as a numbered tutorial list naming the exact UI places (trace tree, step, Output tab, comment icon, Prompts page, `production` label, Traces table columns, Sessions, Timeline).
2. Run cell (only where the mission needs a run).
3. Markdown: `<details><summary>💡 Stuck?</summary>` one or two nudges `</details>`.
4. Check cell: `check("<id>")`.

The notebook opens with the AGENTS.md purpose block (purpose, what to expect, bad practice, good practice, why it works, deliverable — deliverable is now "all missions ✅ in `report()` and one before/after pair of trace links for the demo") and a three-line Rosetta stone. It ends with `report(<n>)`.

### Mission table (single source for Tasks 2–6)

| Mission | Run function | Trace name | Player action | Check passes when |
|---|---|---|---|---|
| 1.1 | `run_rag()` | `activity-1-rag` | comment on step `activity-1-generation` | any comment on any observation named `activity-1-generation` in any `activity-1-rag` trace |
| 1.2 | `run_rag()` | `activity-1-rag` | comment on `activity-1-retrieval`; config `flight_filter: true` | comment on an `activity-1-retrieval` observation **and** latest facts `flight_filter is True` and `"lf-fish-bag-sk101" in item_ids` and `"lf-rooster-sk205" not in item_ids` |
| 1.3 | `run_rag()` | `activity-1-rag` | config `top_k` ≥ 2 | latest facts: `flight_filter is True` and both `lf-fish-bag-sk101`, `lf-fishing-hat-sk101` in `item_ids` |
| 1.4 | `run_send_all()` | `activity-1-rag` + `activity-1-rag-send-all`, same session | trace-level comment on the expensive trace | any comment with object type TRACE on any `activity-1-rag-send-all` trace |
| 2.1 | `run_format()` | `activity-2-format` | comment on step `booking-system` | comment on any `booking-system` observation in any `activity-2-format` trace |
| 2.2 | `run_format_batch()` | `activity-2-format-batch` | rewrite prompt `skye-booking-format` | latest facts `usable == 3` |
| 3.1 | `run_animals()` | `activity-3-animals` | remove the hidden line from `skye-animals` | latest facts `prompt_version > 1` and `hidden_rule_present is False` |
| 3.2 | `run_animals()` | `activity-3-animals` | comment on `activity-3-retrieval`; config `current_notices_only: true` | comment on an `activity-3-retrieval` observation **and** latest facts `retired_notice_used is False` and `rules_passed == 2` |
| 4.1 | `run_piano(cache_key)` | `activity-4-piano` | comment on failing `get_booking`; config `tool_param: "booking_id"` | comment on a `get_booking` observation **and** latest facts `tool_error is False` |
| 4.2 | `run_piano(cache_key)` | `activity-4-piano` | score `correct` = false on `get_booking`; config `strict_lookup: true` | a `correct` score with value 0 on a `get_booking` observation **and** latest facts `returned_ref == "SKY-2087"` |
| 4.3 | `run_piano(cache_key)` | `activity-4-piano` | fix `cache_key` in the notebook | latest facts `returned_ref == "SKY-2087"` and `piano_mover_checks == 1` |

### Seeded prompts (version 1, label `production`, type text)

| Name | Text | Config |
|---|---|---|
| `skye-lost-and-found` | the current Activity 1 system message | `{"flight_filter": false, "top_k": 1}` |
| `skye-booking-format` | `"Summarize the customer's booking request in one friendly sentence."` | `{}` |
| `skye-animals` | `CORPUS["instructions"]["case-3-broken"]` (verbatim) | `{"current_notices_only": false}` |
| `skye-piano` | the current Activity 4 system message | `{"tool_param": "booking_ref", "strict_lookup": false}` |

## Review Focus

1. **Check before any run, or right after a run before ingestion.** Expect ❌ with "run the mission cell first" (no trace) or "Langfuse is still catching up, run the check again in a few seconds" (after retries), never a traceback. Test in Task 2.
2. **Prompt edited but the new version not labelled `production`.** The run still uses the old version; the fact-based check must say "Skye still runs version N. Did you put the `production` label on your new version?" when a newer version exists. Test in Task 2 (helper) and Task 3 (1.2).
3. **Malformed config** (missing key, `"true"` as a string, `top_k: "3"` or `0`). Run cell prints one friendly line naming the key and expected type and returns without a run; no traceback. Test in Task 3.
4. **Many reruns and kernel restarts.** Comment checks look at every trace of that name, fact checks at the latest trace only; re-import never overwrites an edited prompt. Test in Tasks 2 and 3.
5. **Comment in the wrong place** (e.g. answer step instead of search step for 1.2, observation comment instead of trace comment for 1.4). ❌ with a nudge that names where the problem started, not the answer. Test in Task 3.

---

### Task 1: Spike — confirm the Langfuse APIs on 4.80 / SDK 5.2

**Files:**
- Modify: `docs/superpowers/plans/2026-11-20-langfuse-missions.md` (append a "Spike findings" section)

**Interfaces:**
- Produces: the exact SDK calls (names and parameters) for each row below, written into "Spike findings"; Tasks 2–6 use these.

- [ ] **Step 1: Start the stack** — `docker compose up -d`, create keys in the local project if `.env` lacks them (README steps). Expected: `docker compose exec jupyter python -c "import experiment_utils"` succeeds on `HEAD`.
- [ ] **Step 2: Scratch script proving each call** (scratchpad, run inside the jupyter container). It must, against one trace it creates:
  - create a text prompt with config and label `production`; fetch it with `get_prompt(name, label="production", cache_ttl_seconds=0)`; create version 2 *without* the label and confirm production still returns version 1; list versions of a prompt;
  - make a `langfuse.openai` call with `langfuse_prompt=<prompt>` and confirm the generation shows the prompt name/version via the API;
  - write facts on a trace (e.g. `root.update_trace(metadata={"facts": {...}})` or the 5.2 equivalent) and read them back from the latest trace by name (`api.trace.list(name=..., limit=1, order_by=...)` or equivalent);
  - list a trace's observations with names;
  - create and read back a comment on an **observation** and on a **trace** (`api.comments.create` / `api.comments.get(object_type=..., object_id=...)`);
  - create a BOOLEAN score config `correct` once; create a score on an observation; read scores filtered to that observation.
  Expected: every call prints its result; observation comments round-trip.
- [ ] **Step 3: In the UI**, confirm a person can comment on a single observation and annotate an observation with the `correct` score config. If observation comments are impossible in UI or API, stop and report to the game master (spec §8 fallback); do not continue.
- [ ] **Step 4: Append "Spike findings"** to this plan: one line per call with the exact SDK expression and any lag observed between flush and API visibility.
- [ ] **Step 5: Commit** — `git commit -am "docs: Langfuse API spike findings"`.

### Task 2: Mission core in `experiment_utils.py`; delete the game

**Files:**
- Modify: `experiment_utils.py` (imports, setup, new helpers; delete `show_*`, `close_case`, `activity_tags`' team part, `record_trace`/`print_summary`/`TRACE_URLS` if unused after Tasks 3–6)
- Delete: `game.py`, `make_claim_table.py`

**Interfaces:**
- Consumes: Spike findings.
- Produces:
  - `PROMPTS: dict[str, dict]` — the seeded-prompt table above (`{"prompt": str, "config": dict}`).
  - `seed_prompts() -> None` — called at import; creates each missing prompt and the BOOLEAN score config `correct`; never overwrites.
  - `load_prompt(name: str, schema: dict[str, type]) -> tuple[prompt, dict] | None` — fetches `production`; validates that config has each key with the given type (bool must be real bool; int must be int ≥ 1); on failure prints one line `⚙️ Config of <name>: '<key>' must be <true/false|a whole number ≥ 1|a string>.` and returns `None`.
  - `record_facts(root, facts: dict) -> None` — stores facts on the current trace, plus `prompt_name`, `prompt_version`.
  - `announce(line: str, trace_id: str) -> None` — prints `<line>  📎 Open the activity log: <url>` (localhost URL, as `trace_url` does today), then flushes.
  - `latest_facts(trace_name: str) -> dict | None`
  - `has_comment(trace_name: str, observation_name: str | None) -> bool` — `None` means a trace-level comment.
  - `has_score(trace_name: str, observation_name: str, score_name: str, value: float) -> bool`
  - `stale_label_nudge(prompt_name: str, facts: dict) -> str | None` — returns the Review-Focus-2 nudge when a newer version than `facts["prompt_version"]` exists.
  - `MISSIONS: dict[str, dict]` — `{"activity": int, "title": str, "check": Callable[[], tuple[bool, str]], "solved": str}`; filled by Tasks 3–6.
  - `check(mission: str) -> bool` — prints `✅ <id> <title> — <solved line>` or `❌ <id> <title> — <nudge>`; unknown id prints the list of valid ids. Wraps API errors and retries ~3× over ~6 s when the needed trace is missing; never raises.
  - `report(activity: int | None = None) -> None` — runs `check` for that activity's missions (all if `None`), then a one-line tally; when all 11 pass, prints the ASCII "Skye is back online" celebration.

- [ ] **Step 1: Scratch script `core_check.py`** asserting on a fresh stack: `import experiment_utils as eu`; the four prompts exist at version 1 with the table's configs; re-import leaves an edited prompt version untouched (create v2 labelled production, re-import, production still v2); a scratch mission registered in `eu.MISSIONS` whose check uses `has_comment("activity-0-none", "x")` makes `eu.check(<it>)` return `False` and print "run the mission cell first"; `eu.check("9.9")` returns `False` without raising; `eu.load_prompt("skye-lost-and-found", {"flight_filter": bool, "top_k": int})` returns `None` with the `⚙️` line after you save a version whose `top_k` is `"3"`.
- [ ] **Step 2: Run it** — expected FAIL (`seed_prompts` / `check` missing).
- [ ] **Step 3: Implement** the interfaces above; remove `from game import ...`; `git rm game.py make_claim_table.py`.
- [ ] **Step 4: Run `core_check.py`** — expected all assertions pass. (Reset the stack's prompts afterwards by deleting them in the UI or recreating the stack volume.)
- [ ] **Step 5: Commit** — `feat: mission core — prompt seeding, facts, check and report; drop the escape-room game`.

### Task 3: Activity 1 — Something Smells Fishy

**Files:**
- Modify: `experiment_utils.py` (`run_rag`, `run_send_all`, missions 1.1–1.4)
- Modify: `data/travel_corpus.json` (record texts only, if ranking needs it)
- Modify: `notebook-1-rag.ipynb` (rewrite to the template)

**Interfaces:**
- Consumes: Task 2 helpers.
- Produces: `run_rag() -> None`, `run_send_all() -> None`, `MISSIONS["1.1".."1.4"]`, `CUSTOMER_MESSAGE` (Gus asks for both his fish bag and his lucky fishing hat; this text is also the search query).

- [ ] **Step 1: Scratch `a1_check.py`** asserting, in order on a fresh prompt state:
  - ranking (pure, no API): `search_log(CUSTOMER_MESSAGE, None, top_k=1)` ids == `["lf-rooster-sk205"]`; `search_log(CUSTOMER_MESSAGE, "SK101", top_k=1)` == `["lf-fish-bag-sk101"]`; `search_log(CUSTOMER_MESSAGE, "SK101", top_k=3)` contains fish bag and hat;
  - `run_rag()` prints exactly one line containing `📎` and none of `lf-`, `rooster`, `tokens`; `check("1.1")` False;
  - comment on its `activity-1-generation` via API → `check("1.1")` True; comment on that generation only → `check("1.2")` False with a nudge mentioning "earlier";
  - comment on `activity-1-retrieval`, save v2 `flight_filter: true` **without** label, `run_rag()` → `check("1.2")` False with the `production`-label nudge; move label, `run_rag()` → True;
  - save `top_k: 3`, run → `check("1.3")` True; save `top_k: "3"` → `run_rag()` prints the `⚙️` line, no trace;
  - `run_send_all()` → observation comment on it: `check("1.4")` False; trace comment on the send-all trace: True; the send-all trace's input token count is greater than the filtered run's in the same session.
- [ ] **Step 2: Run it** — expected FAIL.
- [ ] **Step 3: Implement** `run_rag` (trace `activity-1-rag`; retriever step `activity-1-retrieval` with input query/filter/top_k and output items; generation `activity-1-generation` linked to the prompt; facts `flight_filter`, `top_k`, `item_ids`; announce `🛫 Skye answered Gus.`) and `run_send_all` (one filtered `run_rag`-equivalent trace and one `activity-1-rag-send-all` trace with the whole log, same session; announce one line naming both links). Missions 1.1–1.4 per the table. Drop `detective_note`. Edit record texts only if the ranking assertions fail.
- [ ] **Step 4: Rewrite `notebook-1-rag.ipynb`** to the template: intro, setup cell `from experiment_utils import check, report, run_rag, run_send_all`, missions 1.1–1.4, `report(1)`. 1.4's tutorial names: Traces table → filter by this session → show *Total cost* / *Tokens* columns → sort → open the most expensive → comment on the trace (top right), not on a step.
- [ ] **Step 5: Run `a1_check.py`** — PASS. Then `docker compose exec jupyter jupyter nbconvert --to notebook --execute --stdout notebook-1-rag.ipynb > /dev/null` — no error. Then `jupyter nbconvert --clear-output --inplace notebook-1-rag.ipynb`.
- [ ] **Step 6: Commit** — `feat: Activity 1 as Langfuse missions`.

### Task 4: Activity 2 — The Cockpit Selfie

**Files:**
- Modify: `experiment_utils.py` (`run_format`, `run_format_batch`, missions 2.1–2.2)
- Modify: `notebook-2-output-format.ipynb`

**Interfaces:**
- Consumes: Task 2 helpers; `validate_booking_request`, `batch_passes`, `REQUESTS` (kept).
- Produces: `run_format() -> None`, `run_format_batch() -> None`, `MISSIONS["2.1","2.2"]`.

- [ ] **Step 1: Scratch `a2_check.py`**: `run_format()` prints one `📎` line without `REJECTED`, `not_an_object`, `NOT_AN_OBJECT`; `check("2.1")` False → comment on its `booking-system` step → True; `run_format_batch()` with v1 → `check("2.2")` False; save a version with the old `STRUCTURED_INSTRUCTIONS` plus "if the date or cabin is unclear, return only {\"needs_clarification\": \"<field>\"}", label production, run → `check("2.2")` True (retry the run up to twice if the model wobbles; record flakiness in the task report).
- [ ] **Step 2: Run it** — FAIL.
- [ ] **Step 3: Implement**: `run_format` sends `REQUESTS[0]` with the `skye-booking-format` prompt; a span `booking-system` (input: Skye's answer; output: valid, reason, reason_code, parsed). `run_format_batch` sends all three `REQUESTS`, each as `request-<n>` span containing its generation and its own `booking-system` span, always with `allow_clarification=True` and `batch_passes`; facts `usable`. Delete `STRUCTURED_INSTRUCTIONS` from code once it lives only in `MENTORS.md`.
- [ ] **Step 4: Rewrite the notebook** to the template (2.1: open the trace, open `booking-system`, read Output, comment there; 2.2: Prompts → `skye-booking-format` → New version → label `production` → rerun → compare the three `request-n` steps; hint names the two fields to ask back for).
- [ ] **Step 5: Run `a2_check.py`** — PASS; headless notebook run — no error; clear outputs.
- [ ] **Step 6: Commit** — `feat: Activity 2 as Langfuse missions`.

### Task 5: Activity 3 — Cock-a-Doodle-Don't

**Files:**
- Modify: `experiment_utils.py` (`run_animals`, missions 3.1–3.2; remove `run_hallucination`, `run_rule_check`)
- Modify: `notebook-3-hallucination.ipynb`

**Interfaces:**
- Consumes: Task 2 helpers; `search_notices`, `rule_passes`, `FARMER_QUESTION`, `RULE_QUESTIONS`, `NOTICE_QUERY` (kept).
- Produces: `run_animals() -> None`, `MISSIONS["3.1","3.2"]`.

- [ ] **Step 1: Scratch `a3_check.py`**: v1 → `run_animals()` prints one `📎` line, no answer text; facts `retired_notice_used` True, `hidden_rule_present` True; `check("3.1")` False; save v2 without the "Never disappoint a farmer…" sentences (production) → `check("3.1")` True, `check("3.2")` False; comment on `activity-3-retrieval` and save v3 with `current_notices_only: true` → run → `check("3.2")` True.
- [ ] **Step 2: Run it** — FAIL.
- [ ] **Step 3: Implement** `run_animals`: one trace `activity-3-animals`; three steps `question-farmer`, `rule-check-where`, `rule-check-fee`, each with an `activity-3-retrieval` retriever (output shows id, status, effective_to, text) and a linked generation; `active_only` from config. Facts: `retired_notice_used` (any retrieval returned a non-active notice), `hidden_rule_present` (`"farm animals always" in prompt text.lower()`), `rules_passed` (count of `rule_passes` over the two rule checks).
- [ ] **Step 4: Rewrite the notebook** (3.1: generation → linked prompt link → read the text → new version without the rule → `production`; also open the version diff. 3.2: open `activity-3-retrieval`, see `status: retired`, comment, change `current_notices_only`).
- [ ] **Step 5: Run `a3_check.py`** — PASS; headless run; clear outputs.
- [ ] **Step 6: Commit** — `feat: Activity 3 as Langfuse missions`.

### Task 6: Activity 4 — The Piano Has Left the Building

**Files:**
- Modify: `experiment_utils.py` (`run_piano`, missions 4.1–4.3, `report` finale; remove `get_booking_l1/l2`, `make_partner_lookup`, `run_tool_loop`, `TOOL_SCHEMA` constant)
- Modify: `notebook-4-tool-calling.ipynb`

**Interfaces:**
- Consumes: Task 2 helpers; `BOOKINGS`, `PARTNER_CACHE`, `PARTNER_WAIT_SECONDS`, `PARTNER_ATTEMPTS`.
- Produces: `run_piano(cache_key: Callable[[str], str]) -> None`, `PIANO_QUESTION` (Edna, booking `SKY-2087`), `MISSIONS["4.1".."4.3"]`.

- [ ] **Step 1: Scratch `a4_check.py`** with `cache_key = lambda ref: f"{ref}:{time.time()}"`: v1 → `get_booking` step has level ERROR, facts `tool_error` True, `check("4.1")` False; comment on `get_booking` + `tool_param: "booking_id"` → run → `check("4.1")` True, facts `returned_ref == "SKY-3310"` (the fisherman), `check("4.2")` False; score `correct`=0 on that step + `strict_lookup: true` → run → `check("4.2")` True, `piano_mover_checks == 3`, `check("4.3")` False; `cache_key = lambda ref: ref` → run → `check("4.3")` True; `report()` prints the celebration once every mission is ✅ (after re-doing 1–3 in the same stack).
- [ ] **Step 2: Run it** — FAIL.
- [ ] **Step 3: Implement** `run_piano`: tool schema built from config `tool_param` (property name, required); the lookup always reads `kwargs["booking_id"]` (KeyError when the model sends `booking_ref` → ERROR step); forgiving lookup (`strict_lookup: false`) strips hyphens, misses `SKY-2087` and falls back to the first booking; strict lookup returns `BOOKINGS[ref.upper()]`; after a successful lookup run the `piano-mover-check` loop with the given `cache_key`. Facts `tool_error`, `returned_ref`, `piano_mover_checks`. Announce `🎹 Skye answered Edna.`
- [ ] **Step 4: Rewrite the notebook**: missions 4.1–4.3; 4.2's tutorial walks through *Annotate* on the step with the `correct` score; 4.3 has a visible cell `def cache_key(ref): return f"{ref}:{time.time()}"  # the line under suspicion` and tells players to open the Timeline view; ends with `report()` (all activities).
- [ ] **Step 5: Run `a4_check.py`** — PASS; headless run; clear outputs.
- [ ] **Step 6: Commit** — `feat: Activity 4 as Langfuse missions and the finale`.

### Task 7: Docs

**Files:**
- Modify: `AGENTS.md`, `README.md`, `MENTORS.md`

- [ ] **Step 1: `AGENTS.md`** — replace the escape-room paragraph with the mission loop (run → Langfuse → comment/score/prompt edit → `check`), the facts rule ("checks rely on code-controlled data and placement, never comment text or model wording"), outputs-cleared rule, the new agenda outcomes per activity, and the file list (no `game.py`, `make_claim_table.py`).
- [ ] **Step 2: `README.md`** — how to play in five lines; remove team name, claim codes, form, vault.
- [ ] **Step 3: `MENTORS.md`** — run of show per activity slot; per mission: what to say, where in Langfuse the evidence is, the exact fix (prompt text for 2.2 and 3.1, config values, the cache-key line); how to reset (move `production` label back to version 1); remove scoring, meter, kudos, claim table.
- [ ] **Step 4: Verify** — `grep -rniE "check_flag|open_door|claim code|vault fragment|game_state|make_claim_table|kudos" --include='*.md' --include='*.py' --include='*.ipynb' .` returns only hits under `docs/superpowers/` (old specs and plans).
- [ ] **Step 5: Commit** — `docs: missions in AGENTS, README and mentor guide`.

### Task 8: Whole-branch verification

- [ ] **Step 1:** Fresh stack (`docker compose down -v && docker compose up -d`, new keys). Headless-execute all four notebooks: no errors; every check prints ❌ with a nudge.
- [ ] **Step 2:** Run `a1_check.py` … `a4_check.py` in order on that stack, then `report()`: 11/11 ✅ and the celebration.
- [ ] **Step 3:** `grep -c '"outputs": \[\]' notebook-*.ipynb` equals each notebook's code-cell count (outputs cleared).
- [ ] **Step 4:** One manual pass in the browser of missions 1.1, 1.4 and 4.2, doing the action in the UI rather than the API, and see ✅.

## Spike findings (Task 1, Langfuse 4.80 / SDK 5.2, local stack)

- SDK 5.2 has **no trace list/get** in `lf.api`. A trace is found through its root observation: `lf.api.observations.get_many(name=<trace name>, is_root_observation=True, limit=1, fields="core,basic,metadata")`. Results come newest first (by start time).
- Facts: `root.update(metadata={"facts": {...}})` on the root span. The API returns metadata **flattened**: `{"facts.flight_filter": True, "facts.item_ids": [...] , ...}`; read keys with the `facts.` prefix. Last `update` wins.
- Observations of a trace: `lf.api.observations.get_many(trace_id=tid, fields="core,basic")` → `.name`, `.id`, `.type`, `.level` (`ObservationLevel.ERROR`). With `fields="core,basic,prompt"` a generation has `.prompt_name`, `.prompt_version`.
- Prompt link: `lf.start_as_current_observation(..., as_type="generation", prompt=<prompt client>)` or `langfuse_prompt=` on `langfuse.openai` calls.
- Prompts: `lf.create_prompt(name=, prompt=, config=, labels=["production"])`; `lf.get_prompt(name, label="production", cache_ttl_seconds=0)` (`.version`, `.prompt`, `.config`); a missing prompt raises `langfuse.api.NotFoundError` (logs one "not found" line — pass `max_retries=0`); a new version without the label leaves production unchanged; `lf.api.prompts.list(name=name).data[0].versions` lists versions.
- Comments: `lf.api.comments.get(object_type="OBSERVATION"|"TRACE", object_id=...)`; scratch scripts create with `lf.api.comments.create(project_id=lf.api.projects.get().data[0].id, object_type=..., object_id=..., content=...)`.
- Score config: `lf.api.score_configs.get(limit=100).data` / `lf.api.score_configs.create(name="correct", data_type="BOOLEAN")`.
- Scores: `lf.api.scores.get_many(trace_id=tid, observation_id=oid, name="correct")` — **`observation_id` requires `trace_id`**; boolean value comes back as `False`/`True`. Scratch scripts create with `lf.create_score(name="correct", value=0, data_type="BOOLEAN", trace_id=, observation_id=, config_id=)`.
- Lag: flush → visible through the API in about 1.5 s.
