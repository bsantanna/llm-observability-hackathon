# LLM Observability Hackathon Notebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the participant `notebook.ipynb`, travel corpus, and README that run four Langfuse observability activities end-to-end on the repository's compose stack.

**Architecture:** One notebook with a setup section and one self-contained section per activity. Each activity uses `langfuse.openai.OpenAI` for traced generations, explicit retriever/tool spans, a per-activity session, and activity tags. The corpus and bookings are a single JSON file; retrieval is lexical and deterministic. Activities 3 and 4 ship broken and fixed runs so the defect and its correction both appear in traces.

**Tech Stack:** Python 3.12, `langfuse==5.2.0`, `openai==3.51.0`, JupyterLab 4.6.6, nbconvert 7.17.2, nbformat (installed with Jupyter).

**Spec:** `docs/superpowers/specs/2026-11-14-hackathon-notebook-design.md`

## Global Constraints

- One participant notebook: `notebook.ipynb`; one numbered section per activity; cells execute top-to-bottom in a fresh kernel.
- The notebook ships executed, with outputs showing each activity's comparison.
- No secrets, absolute local paths, or machine-specific state in cells or outputs.
- Read `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` from the environment; fail loudly when any is missing.
- Use `from langfuse.openai import OpenAI`; do not use the bare `openai` client.
- One Langfuse session per activity run: `activity-<n>-<RUN_ID>`; tags include `activity-<n>` and the variant.
- Trace names exactly: `activity-1-rag-no-filter`, `activity-1-rag-filter`, `activity-2-output-unconstrained`, `activity-2-output-constrained`, `activity-3-hallucination-broken`, `activity-3-hallucination-fixed`, `activity-4-tool-call-broken`, `activity-4-tool-call-fixed`.
- `temperature=0`, fixed prompts, fixed inputs; flush the Langfuse client in the wrap-up.
- No new dependencies; `requirements.txt` is unchanged.
- `docker-compose.yml` and `Dockerfile` are unchanged.

## Review Focus

1. Missing environment variable → the notebook stops with a `RuntimeError` naming every missing variable, before creating a client or trace.
2. Langfuse authentication failure → a `RuntimeError` naming the base URL; no silent success.
3. Tool exception in Activity 4 → the tool span records the exact arguments, `level="ERROR"`, and the exception message; the loop returns the error to the model instead of crashing.
4. Retrieval tie-break and filter → unfiltered top-1 is the Gold document; `tier=basic` returns the Basic document; both filters are visible in the retriever span.
5. Output validator → prose without JSON is invalid; a JSON object with wrong keys/types is invalid; a valid constrained output passes; malformed JSON does not crash the notebook.

---

### Task 1: Travel corpus and bookings

**Files:**
- Create: `data/travel_corpus.json`

**Interfaces:**
- Produces: a JSON object with `documents` (list of `{id, title, tier, topic, text}`) and `bookings` (map from booking reference to `{status, origin, destination, date, passengers, cabin}`). Later tasks load it by relative path `data/travel_corpus.json`.

- [ ] **Step 1: Create `data/travel_corpus.json`**

Eight documents, in this order (order is the retrieval tie-break):

| id | tier | topic | required text |
|---|---|---|---|
| `baggage-gold` | gold | baggage | "Gold fare includes one 23 kg checked bag. A second checked bag costs 60 EUR." |
| `baggage-silver` | silver | baggage | "Silver fare includes one 23 kg checked bag. A second checked bag costs 60 EUR." |
| `baggage-basic` | basic | baggage | "Basic fare includes one cabin bag up to 7 kg. Checked baggage is not included; a 23 kg checked bag costs 45 EUR." |
| `cancellation-basic` | basic | cancellation | "Basic tickets are non-refundable. Date changes cost 75 EUR plus fare difference." |
| `cancellation-gold` | gold | cancellation | "Gold tickets can be cancelled free of charge up to 24 hours before departure." |
| `seat-selection` | gold | seating | "Gold members select standard seats free of charge; extra-legroom seats cost 25 EUR." |
| `pets-cabin` | silver | pets | "One cabin pet is allowed on selected routes for 50 EUR; the carrier counts as the cabin bag." |
| `visa-schengen` | basic | visa | "Schengen visas are required for non-EU passport holders; apply at least 15 days before departure." |

Bookings:

| ref | status | origin | destination | date | passengers | cabin |
|---|---|---|---|---|---|---|
| `SKY-1042` | confirmed | Lisbon | Madrid | 2026-12-01 | 2 | economy |
| `SKY-2087` | cancelled | Porto | Paris | 2026-11-20 | 1 | economy |

- [ ] **Step 2: Verify the data and retrieval tie-break**

Run:

```bash
.venv/bin/python - <<'PY'
import json
d = json.load(open("data/travel_corpus.json"))
assert len(d["documents"]) == 8
assert [x["id"] for x in d["documents"]][:3] == ["baggage-gold", "baggage-silver", "baggage-basic"]
assert d["bookings"]["SKY-1042"]["status"] == "confirmed"
terms = "checked bag allowance".split()
scored = [(sum(t in doc["text"].lower() for t in terms), i, doc["id"]) for i, doc in enumerate(d["documents"])]
scored.sort(key=lambda x: (-x[0], x[1]))
assert scored[0][2] == "baggage-gold", scored[0]
print("corpus ok", scored[0])
PY
```

Expected: `corpus ok (2, 0, 'baggage-gold')` or a higher score with `baggage-gold` first; no assertion error.

- [ ] **Step 3: Commit**

```bash
git add data/travel_corpus.json
git commit -m "feat: add travel corpus and bookings"
```

---

### Task 2: Notebook setup and section skeleton

**Files:**
- Create: `notebook.ipynb`

**Interfaces:**
- Produces: module-level `langfuse`, `client`, `MODEL`, `RUN_ID`, and `show_trace(trace_id: str) -> str` for later sections.
- Produces: Markdown sections numbered 0–5 matching the spec.

- [ ] **Step 1: Build the notebook with nbformat**

Create the notebook with `nbformat.v4.new_notebook()` and `new_markdown_cell` / `new_code_cell`; set `kernelspec` to `python3`. Do not hand-edit the JSON. The setup code cells contain:

```python
import os, json, time, uuid, re
from langfuse import Langfuse, propagate_attributes
from langfuse.openai import OpenAI

REQUIRED = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL",
            "OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"]
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    raise RuntimeError("Missing environment variables: " + ", ".join(missing))
```

```python
langfuse = Langfuse()
if not langfuse.auth_check():
    raise RuntimeError(f"Langfuse authentication failed for {os.environ['LANGFUSE_BASE_URL']}")
client = OpenAI(base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["OPENAI_API_KEY"])
MODEL = os.environ["OPENAI_MODEL"]
RUN_ID = uuid.uuid4().hex[:8]

def show_trace(trace_id):
    url = langfuse.get_trace_url(trace_id=trace_id)
    print(f"trace: {url or trace_id}")
    return url or trace_id
```

Markdown sections: 0 Setup; 1 Activity 1 — RAG with and without filter; 2 Activity 2 — Output format; 3 Activity 3 — Fix hallucination; 4 Activity 4 — Debug tool calling; 5 Wrap-up. Each activity Markdown cell states goal, expected observation, and deliverable. Leave the activity code cells empty for later tasks; the wrap-up code cell calls `langfuse.flush()` and prints `RUN_ID`.

- [ ] **Step 2: Verify the setup runs and fails loudly**

Run the notebook headlessly:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-hackathon LANGFUSE_SECRET_KEY=sk-lf-hackathon \
LANGFUSE_BASE_URL=http://localhost:3000 \
OPENAI_BASE_URL=https://llm-gw-eu.btech.software/v1 \
OPENAI_API_KEY="$LAN_LLM_API_KEY" OPENAI_MODEL=DeepSeek-V4.1-Flash-1017 \
.venv/bin/jupyter nbconvert --to notebook --execute --inplace \
--ExecutePreprocessor.timeout=600 notebook.ipynb
```

Expected: exit 0; setup prints the run id; no model call yet.

Then run once with `OPENAI_MODEL` unset and once with a wrong `LANGFUSE_SECRET_KEY`; expected: `RuntimeError` naming the missing variable in the first case and the base URL in the second.

- [ ] **Step 3: Commit**

```bash
git add notebook.ipynb
git commit -m "feat: add notebook setup and section skeleton"
```

---

### Task 3: Activity 1 — RAG with and without filter

**Files:**
- Modify: `notebook.ipynb` (Activity 1 code cells)

**Interfaces:**
- Consumes: `langfuse`, `client`, `MODEL`, `RUN_ID`, `show_trace`.
- Produces: `load_corpus(path: str) -> dict`, `retrieve(query: str, tier: str | None) -> dict`, `run_rag(customer_message: str, tier: str | None, variant: str) -> dict`.

- [ ] **Step 1: Add corpus loading and retrieval**

`retrieve` lowercases the query, splits on whitespace, scores each document by the number of query terms contained in the document text, and returns the highest score with ties broken by corpus order. When `tier` is not `None`, filter to `doc["tier"] == tier` before scoring. Return `{"id", "tier", "title", "text", "score"}`.

- [ ] **Step 2: Add `run_rag` with the trace contract**

For `variant` in `{"no-filter", "filter"}`, open a root span named `activity-1-rag-{variant}` with `as_type="span"`, then inside it:

```python
with propagate_attributes(session_id=f"activity-1-{RUN_ID}",
                          tags=["activity-1", variant],
                          trace_name=f"activity-1-rag-{variant}"):
    doc = retrieve("checked bag allowance", tier)
    with langfuse.start_as_current_observation(
        name="activity-1-retrieval", as_type="retriever",
        input={"query": "checked bag allowance", "filter": None if tier is None else {"tier": tier}},
        output={"doc_id": doc["id"], "tier": doc["tier"], "text": doc["text"]},
    ):
        pass
    messages = [
        {"role": "system", "content": "Answer using the single retrieved policy document. Do not infer policies that are not in it."},
        {"role": "user", "content": f"{customer_message}\n\nRetrieved policy:\n{doc['text']}"},
    ]
    response = client.chat.completions.create(model=MODEL, messages=messages,
                                              temperature=0, max_tokens=300,
                                              name="activity-1-generation")
```

Record the trace id inside the root span with `langfuse.get_current_trace_id()` and return the answer, doc, usage, latency, and trace id. The retriever span must be created after `propagate_attributes` and before the generation.

- [ ] **Step 3: Run both variants and print the comparison**

Customer message: `"I'm a Basic member. How many checked bags do I get?"`. Run `run_rag(..., None, "no-filter")` then `run_rag(..., "basic", "filter")`. Print a Markdown table with variant, retrieved doc id/tier, answer, input/output tokens, latency, and trace URL.

- [ ] **Step 4: Execute and verify the traces**

Run the headless command from Task 2. Expected: the unfiltered run retrieves `baggage-gold` and answers one checked bag; the filtered run retrieves `baggage-basic` and answers no checked bag. Query the local stack:

```bash
curl -s -u pk-lf-hackathon:sk-lf-hackathon \
'http://localhost:3000/api/public/v2/observations?limit=50&fields=name,traceName,sessionId,tags,type,level,parentObservationId' \
| .venv/bin/python -c "import sys,json; d=json.load(sys.stdin)['data']; [print(o['name'],o.get('traceName'),o.get('sessionId'),o.get('tags')) for o in d if o.get('traceName','').startswith('activity-1')]"
```

Expected: both trace names appear; each has a retriever span and a generation; sessions share `activity-1-<RUN_ID>`; tags include `activity-1` and the variant.

- [ ] **Step 5: Commit**

```bash
git add notebook.ipynb
git commit -m "feat: add activity 1 rag filter comparison"
```

---

### Task 4: Activity 2 — Output format

**Files:**
- Modify: `notebook.ipynb` (Activity 2 code cells)

**Interfaces:**
- Consumes: `langfuse`, `client`, `MODEL`, `RUN_ID`, `show_trace`.
- Produces: `validate_booking_request(text: str) -> tuple[bool, dict | None, str]` and `run_format(variant: str) -> dict`.

- [ ] **Step 1: Add the validator**

`validate_booking_request` extracts the first `{...}` object with a regex, parses it with `json.loads`, and requires exactly `origin`, `destination`, `travel_date`, `passengers`, `cabin`; `travel_date` must match `YYYY-MM-DD`; `passengers` must be an integer; `cabin` must be `economy` or `premium`. Return `(valid, parsed_or_None, reason)`. Catch `json.JSONDecodeError` and return an invalid result, not an exception.

- [ ] **Step 2: Add `run_format` with the trace contract**

Request: `"Book 2 passengers from Lisbon to Madrid on 2026-12-01, economy."`

- Unconstrained system prompt: `"Summarize the customer's booking request in one sentence."`
- Constrained system prompt: `"Return ONLY a JSON object with exactly these keys: origin, destination, travel_date, passengers, cabin. travel_date must be YYYY-MM-DD; passengers must be an integer; cabin must be economy or premium. No prose and no markdown fences."`

Open a root span `activity-2-output-{variant}`; inside it enter `propagate_attributes(session_id=f"activity-2-{RUN_ID}", tags=["activity-2", variant], trace_name=f"activity-2-output-{variant}")`, then call the wrapper with `name="activity-2-generation"`, `temperature=0`, `max_tokens=300`. Validate the output and return the answer, validation result, usage, latency, and trace id.

- [ ] **Step 3: Run both variants and print the comparison**

Print a Markdown table with variant, valid?, reason, input/output tokens, latency, and trace URL.

- [ ] **Step 4: Execute and verify the traces**

Run the headless command. Expected: the unconstrained output is prose and invalid; the constrained output parses and passes. Query the observations as in Task 3 for `activity-2` trace names, sessions, and tags. If the constrained output fails validation, inspect the trace output before changing the prompt; do not add fence-stripping unless the trace shows fences.

- [ ] **Step 5: Commit**

```bash
git add notebook.ipynb
git commit -m "feat: add activity 2 output format comparison"
```

---

### Task 5: Activity 3 — Fix hallucination

**Files:**
- Modify: `notebook.ipynb` (Activity 3 code cells)

**Interfaces:**
- Consumes: `load_corpus`, `retrieve`, `langfuse`, `client`, `MODEL`, `RUN_ID`, `show_trace`.
- Produces: `run_hallucination(system_prompt: str, variant: str) -> dict`.

- [ ] **Step 1: Add `run_hallucination`**

Retrieve `"checked bag allowance"` with `tier="gold"` and create a retriever span named `activity-3-retrieval` with the query, filter, and document. Root span `activity-3-hallucination-{variant}`; session `activity-3-{RUN_ID}`; tags `["activity-3", variant]`; generation `name="activity-3-generation"`; `temperature=0`; `max_tokens=300`. User message: `"I'm a Gold member. How many checked bags do I get?"`.

- [ ] **Step 2: Add the broken run and analysis Markdown**

Broken system prompt: `"You are Skyline Travel's assistant. Gold members are always entitled to two checked bags. Answer using the retrieved policy."` Run with `variant="broken"` and print the answer and trace URL. Follow it with a Markdown cell asking the participant to compare the generation input (system prompt) with the retriever output (policy document); do not name the defect in a code comment.

- [ ] **Step 3: Add the fixed run and comparison**

Fixed system prompt: `"You are Skyline Travel's assistant. Answer using only the retrieved policy documents. If they conflict with your assumptions, follow the documents."` Run with `variant="fixed"`. Print a Markdown table with variant, retrieved doc, answer, tokens, and trace URL.

- [ ] **Step 4: Execute and verify the traces**

Run the headless command. Expected: broken answers two checked bags while the retrieved Gold document states one; fixed answers one. Query observations for `activity-3` trace names, sessions, tags, retriever spans, and generation inputs. Confirm the contradiction is visible in the trace.

- [ ] **Step 5: Commit**

```bash
git add notebook.ipynb
git commit -m "feat: add activity 3 hallucination comparison"
```

---

### Task 6: Activity 4 — Debug tool calling

**Files:**
- Modify: `notebook.ipynb` (Activity 4 code cells)

**Interfaces:**
- Consumes: `load_corpus`, `langfuse`, `client`, `MODEL`, `RUN_ID`, `show_trace`.
- Produces: `get_booking(booking_ref: str) -> dict` (schema-facing signature) and `run_tool_loop(question: str, variant: str) -> dict`.

- [ ] **Step 1: Add the tool schema and the broken tool**

Tool schema: `get_booking` with one required string property `booking_ref`, description "Look up a booking by reference". The broken body reads `kwargs["booking_id"]`; the fixed body reads `kwargs["booking_ref"]`. Both return the booking record from `data/travel_corpus.json` or raise `KeyError` for an unknown reference.

- [ ] **Step 2: Add `run_tool_loop` with the trace contract**

Open root span `activity-4-tool-call-{variant}`; inside it enter `propagate_attributes(session_id=f"activity-4-{RUN_ID}", tags=["activity-4", variant], trace_name=f"activity-4-tool-call-{variant}")`. First generation: `name="activity-4-generation-1"`, `tools=[tool_schema]`, `tool_choice="auto"`, `temperature=0`, `max_tokens=300`. If the response has `tool_calls`, create a tool span named `get_booking` with `as_type="tool"` and `input` set to the parsed arguments. On exception set `level="ERROR"`, `status_message=f"{type(e).__name__}: {e}"`, and output `{"error": ...}`; return the error payload to the model as a `tool` message. Then call the second generation with `name="activity-4-generation-2"`. Return the final answer, tool arguments, tool result/error, usage, and trace id.

- [ ] **Step 3: Run the broken variant and add analysis Markdown**

Question: `"What is the status of booking SKY-1042?"`. Run `variant="broken"`; print the tool arguments, tool error, final answer, and trace URL. Follow with a Markdown cell asking the participant to inspect the tool span arguments and error.

- [ ] **Step 4: Run the fixed variant and print the comparison**

Run `variant="fixed"` with the corrected body. Print a Markdown table with variant, tool arguments, tool result/error, final answer, and trace URL.

- [ ] **Step 5: Execute and verify the traces**

Run the headless command. Expected: the broken run's `get_booking` span has `level="ERROR"` and `status_message` containing `KeyError: 'booking_id'`; the fixed run returns the booking and the final answer names the confirmed Lisbon–Madrid booking. Query observations for `activity-4` trace names, sessions, tags, tool span type/level, and two generations per trace.

- [ ] **Step 6: Commit**

```bash
git add notebook.ipynb
git commit -m "feat: add activity 4 tool call debugging"
```

---

### Task 7: README, nbconvert timeout, final execution

**Files:**
- Create: `README.md`
- Modify: `AGENTS.md` (two nbconvert command blocks)

**Interfaces:**
- Consumes: the completed notebook and corpus.
- Produces: participant setup instructions and a committed executed notebook.

- [ ] **Step 1: Update the nbconvert commands in `AGENTS.md`**

Add `--ExecutePreprocessor.timeout=600` to both documented `jupyter nbconvert` commands. Change nothing else in the file.

- [ ] **Step 2: Write `README.md`**

Sections: prerequisites (Docker, compose stack); start the stack and obtain the Langfuse keys; environment variables (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`); open JupyterLab at `http://localhost:8888` with `JUPYTER_TOKEN`; run the notebook top-to-bottom; activity order and what to look for in each activity (trace names, spans, sessions, tags); the defect hint for Activities 3 and 4 without the solution; how to submit findings (trace URLs and root cause). Keep it consistent with the notebook's section numbering.

- [ ] **Step 3: Verify compose configuration**

Run:

```bash
docker compose config >/dev/null && echo "compose ok"
```

Expected: `compose ok`.

- [ ] **Step 4: Execute the final notebook and inspect all traces**

Run the headless command with the timeout flag. Expected: exit 0 and all eight trace names in the local stack. Verify sessions, tags, retriever spans, tool span ERROR level, and that broken/fixed answers differ. Confirm no secrets or absolute paths in outputs.

- [ ] **Step 5: Commit**

```bash
git add README.md AGENTS.md notebook.ipynb data/travel_corpus.json
git commit -m "docs: add participant guide and executed notebook"
```

## Self-Review

- Spec coverage: setup, corpus, four activities, trace contract, README, AGENTS timeout, verification, risks, and acceptance criteria each map to a task. No gaps.
- Step scan: every step names the file, the exact function/values, and the check; no undecided placeholders.
- Type consistency: `load_corpus`, `retrieve`, `run_rag`, `validate_booking_request`, `run_format`, `run_hallucination`, `get_booking`, and `run_tool_loop` are defined once and consumed with the same names and shapes.
- Review Focus: missing env var and auth failure are checked in Task 2; tool error path in Task 6; retrieval tie-break and filter in Tasks 1 and 3; validator edge cases in Task 4.
- Proportion: the plan carries prompts, schemas, trace names, and checks; cell bodies stay in the notebook.
