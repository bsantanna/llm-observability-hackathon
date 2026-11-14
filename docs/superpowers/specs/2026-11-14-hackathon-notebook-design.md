# Hackathon Notebook Design — LLM Observability

Date: 2026-11-14
Status: draft for review

## Purpose

Build the participant deliverable for the LLM Observability Hackathon: one
`notebook.ipynb` that runs four investigative activities end-to-end against the
repository's self-hosted Langfuse stack and an OpenAI-compatible inference
endpoint. Participants learn to read traces, compare variants, find a
hallucination, and debug a broken tool call.

Audience: participants on a laptop, in one sitting, with keys they create in the
local Langfuse project. Mentors run the same notebook and use its traces for
demonstration and scoring.

Success means the notebook executes top-to-bottom in a fresh kernel with only the
documented environment variables set, and every activity produces a trace a
participant can investigate.

## Scope

Deliverables:

- `notebook.ipynb` — setup, four activity sections, wrap-up; ships executed with
  the comparison outputs committed.
- `data/travel_corpus.json` — fictional travel-policy documents and bookings used
  by the activities.
- `README.md` — participant guide: setup, keys, activity order, what to look for
  in Langfuse, how to submit findings.
- `AGENTS.md` — add `--ExecutePreprocessor.timeout=600` to the two documented
  nbconvert commands. No other change.

Non-goals:

- No embeddings, vector database, or retrieval service; retrieval is lexical and
  in-notebook.
- No application code, services, dashboards, or custom telemetry.
- No test suite; verification is notebook execution plus trace inspection.
- No new dependencies; `requirements.txt` stays unchanged.

## Scenario

Fictional airline "Skyline Travel". The corpus contains tier-scoped policy
documents (`basic`, `silver`, `gold`) and a small booking table. The same scenario
carries all four activities so participants investigate one coherent system.

Corpus documents (8): baggage by tier, cancellation by tier, seat selection, pets,
and a Schengen visa note. Tier baggage rules:

| Tier | Checked bags included |
|---|---|
| basic | 0 (one cabin bag only; a checked bag costs 45 EUR) |
| silver | 1 |
| gold | 1 (a second checked bag costs 60 EUR) |

The Gold baggage document appears first in the corpus. Retrieval scores documents
by token overlap, sorts by score then corpus order, and returns top-1. This makes
the unfiltered Activity 1 retrieval deterministic: all three baggage documents tie
on the query, so the first (Gold) wins.

Bookings: `SKY-1042` (confirmed, Lisbon → Madrid, 2026-12-01, 2 passengers,
economy) plus one or two others for tool variation.

## Notebook structure

Section 0 — Setup (Markdown + code):

- Markdown states prerequisites, required environment variables, and that missing
  keys fail loudly.
- Code validates `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
  `LANGFUSE_BASE_URL`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`;
  raises `RuntimeError` naming every missing variable.
- Initializes `Langfuse()` and `langfuse.openai.OpenAI`, checks
  `langfuse.auth_check()`, creates a run id, and defines `show_trace(trace_id)`.
- All model calls use `temperature=0`, bounded `max_tokens`, fixed prompts, and
  fixed inputs.

Sections 1–4 — one activity each:

- Each starts with a Markdown cell stating the goal, the expected observation, and
  the deliverable.
- Model and tool configuration stays in a small number of cells near the top of
  each section.
- Each section prints only the comparison the activity asks for: answer, retrieved
  document, validation result, tool result, token usage, latency, trace URL.
- Each section runs a broken/variant cell and a second cell, then prints a
  comparison table. Activities 3 and 4 ship with both the defective and fixed runs
  executed, so both traces exist for comparison.

Section 5 — Wrap-up: flush the Langfuse client, print the run's session ids and
trace URLs, and state what participants submit.

## Tracing contract

Every activity uses:

- One session per activity run: `activity-<n>-<run-id>`, where `run-id` is a short
  random value printed in setup.
- Tags: `activity-<n>` plus the variant (`no-filter`/`filter`,
  `unconstrained`/`constrained`, `broken`/`fixed`).
- `propagate_attributes(session_id=..., tags=..., trace_name=...)` entered inside
  the root span, so the generation stays in the same trace. Verified against the
  local stack: child generation parent id resolves inside the root trace.
- Trace names exactly as listed below.

| Activity | Trace name | Spans |
|---|---|---|
| 1 | `activity-1-rag-no-filter` | root span, retriever span (`activity-1-retrieval`), generation |
| 1 | `activity-1-rag-filter` | root span, retriever span (`activity-1-retrieval`), generation |
| 2 | `activity-2-output-unconstrained` | root span, generation |
| 2 | `activity-2-output-constrained` | root span, generation |
| 3 | `activity-3-hallucination-broken` | root span, retriever span, generation |
| 3 | `activity-3-hallucination-fixed` | root span, retriever span, generation |
| 4 | `activity-4-tool-call-broken` | root span, two generations, tool span (`get_booking`, level ERROR) |
| 4 | `activity-4-tool-call-fixed` | root span, two generations, tool span (`get_booking`, success) |

Retriever spans use `as_type="retriever"` with input `{"query": ..., "filter": ...}`
and output `{"doc_id": ..., "tier": ..., "text": ...}`. Tool spans use
`as_type="tool"` with input arguments and output result, or `level="ERROR"` and
`status_message="KeyError: 'booking_id'"` on failure. Generations are created by
the `langfuse.openai` wrapper with activity-specific names; prompts, retrieved
documents, tool arguments, and tool results are attached to the corresponding
span or generation.

## Activity designs

### Activity 1 — RAG with and without filter

Goal: show that retrieval without a tenant/tier filter contaminates the answer.

- User message: Basic member asking how many checked bags are included.
- Retrieval query: "checked bag allowance" (does not mention the tier).
- Unfiltered: top-1 is the Gold baggage document → answer "one checked bag".
- Filtered: `{"tier": "basic"}` → Basic baggage document → answer "no checked bag
  included".
- Comparison table: variant, retrieved doc id/tier, answer, input/output tokens,
  latency, trace URL.

The retriever span input records `filter: null` versus `filter: {"tier": "basic"}`;
the generation input records the retrieved document. No explanatory comment
reveals the defect.

### Activity 2 — Output format

Goal: compare constrained and unconstrained output for a downstream parser.

- Request: "Book 2 passengers from Lisbon to Madrid on 2026-12-01, economy."
- Unconstrained: "Summarize the booking request in one sentence." → prose; the
  validator finds no JSON object and reports invalid.
- Constrained: prompt requires only a JSON object with keys `origin`,
  `destination`, `travel_date`, `passengers`, `cabin`; validator extracts the first
  JSON object and checks keys, types, and ISO date. Expected valid.
- Comparison table: variant, parse/validation result, input/output tokens,
  latency, trace URL.

`response_format` is not used: the prototype gateway rejects JSON-schema and
JSON-object response formats. The lesson is prompt-level format control plus a
downstream validator, and the trace shows the exact emitted bytes.

### Activity 3 — Fix hallucination

Goal: find a prompt-level contradiction in trace data and fix it.

- User message: Gold member asking how many checked bags are included.
- Retrieval: `{"tier": "gold"}` → Gold baggage document states one checked bag.
- Broken system prompt: "Gold members are always entitled to two checked bags.
  Answer using the retrieved policy." → answer "two checked bags".
- Trace shows the system message, the retrieved document, and the contradictory
  answer.
- Fixed system prompt: "Answer using only the retrieved policy documents. If they
  conflict with your assumptions, follow the documents." → answer "one checked
  bag".
- Comparison table: variant, retrieved doc, answer, tokens, trace URL.

The broken cell contains no comment naming the defect; a Markdown cell after it
asks the participant to compare the generation input with the retriever output.

### Activity 4 — Debug tool calling

Goal: diagnose a broken tool call from trace data and repair it.

- Tool schema: `get_booking(booking_ref: string)`.
- Broken implementation reads `kwargs["booking_id"]`; the model calls with
  `{"booking_ref": "SKY-1042"}`. The tool span records the arguments and
  `KeyError: 'booking_id'` at level ERROR. The loop returns the error to the model,
  which produces a second generation explaining it could not retrieve the booking.
- Fixed implementation reads `kwargs["booking_ref"]` and returns the booking;
  the second generation answers with status, route, date, and passenger count.
- Comparison table: variant, tool arguments, tool result/error, final answer,
  trace URL.

The tool function contains no comment naming the mismatch; the trace exposes the
argument key and the exception.

## Error handling

- Missing environment variable → `RuntimeError` listing all missing names.
- Langfuse authentication failure → `RuntimeError` with the base URL.
- Model API errors → propagate; the notebook fails loudly rather than hiding them.
- Validation failures in Activity 2 → reported in the comparison table; they are
  the observation, not an exception.
- Tool exceptions in Activity 4 → captured on the tool span, returned to the model
  as an error payload, and shown in the comparison table.

## Determinism

Fixed corpus order, fixed retrieval query, fixed prompts, `temperature=0`, bounded
`max_tokens`. Model output can still vary across providers; the notebook says so
where it matters. Trace ids and the run id vary per run by design.

## Verification

1. `docker compose config` remains valid (compose is unchanged).
2. Execute the notebook headlessly in a fresh kernel with only the documented
   variables set:
   `jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 notebook.ipynb`.
3. Query the local Langfuse API `/api/public/v2/observations` and confirm the eight
   trace names, their root/child relationships, session ids, tags, retriever and
   tool span types, and the ERROR level on the broken tool span.
4. Confirm Activity 1 answers differ between variants and the filter is visible in
   the retriever span.
5. Confirm Activity 2 unconstrained fails validation and constrained passes.
6. Confirm Activity 3 broken answer contradicts the retrieved document and the
   fixed answer follows it.
7. Confirm Activity 4 broken tool span shows the `KeyError` and the fixed run
   returns booking data and a final answer.
8. Confirm no secrets or absolute local paths appear in cell outputs, and the
   client flush runs at the end.

## Risks

- Inference latency varies (observed 8–60 s per call; one cold call took ~257 s).
  The timeout flag is required; a slow provider can still make the notebook take
  several minutes.
- Cost is `null` unless the Langfuse project has a model definition with pricing
  for the model name. The notebook prints token usage and latency and points to the
  trace for cost.
- The gateway model may not always emit a tool call. The prompt is explicit and
  temperature is 0, but the trace contract depends on the model choosing the tool.
- The generation output's tool-call arguments depend on the wrapper serializing the
  assistant message; if it does not, the tool span still records the exact
  arguments and error.

## Acceptance criteria

- The notebook runs top-to-bottom in a fresh kernel with only documented variables.
- All eight traces appear in Langfuse with the expected spans, sessions, and tags.
- Activities 3 and 4 reproduce the defect before the fix and show the corrected
  behavior after it.
- README section numbering and commands match the notebook.
- The notebook ships executed, with outputs that show each activity's comparison.
- No secrets, absolute paths, or machine-specific state in cells or outputs.
