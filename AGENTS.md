# AGENTS.md

This file is the vendor-neutral coordination contract for AI tooling in this repository.

## Source of Truth

This file is the canonical, vendor-neutral source of truth for shared behavior, domain knowledge, and coordination policy in this repository.

Vendor-specific directories are adapters derived from it, never the source of truth. When present:
- `.claude/CLAUDE.md` — Claude Code adapter; MUST defer to this file.
- `.claude/skills/*/SKILL.md` — tool-scoped skill implementations of shared intent declared here.
- `.mcp.json` — shared MCP server configuration.

No adapter is currently checked in. Add one only when a tool needs mechanics this file cannot express.

Adapters MUST NOT redefine shared rules. Tool-local files such as `.claude/settings.local.json` are not part of the shared contract.

## Cross-Tool Rules

- Keep shared behavior and domain knowledge in this file. Adapters reference it; they do not restate it.
- Treat vendor-specific directories such as `.codex/` as generated or adapter layers.
- Use progressive context loading. Do not preload every skill or specialty document by default.
- When the user asks for a specific specialty such as `notebook`, `langfuse`, `tracing`, or `prompting`, load only the matching adapter context for the active tool.
- If the user uses slash-like syntax such as `/langfuse`, interpret that as an intent to activate the corresponding specialty, even if the current CLI does not support custom slash commands natively.
- Prefer the active tool's native mechanisms for scoped instructions, custom agents, prompts, or subagents instead of forcing another vendor's UX model.

## Subagent Orchestration

Cap concurrent subagents at **4 per fan-out wave**. This is a hard limit, counted across nested subagents; excess work MUST queue into a later wave instead of raising the cap.

Rationale: a hackathon notebook is a single shared file, so parallel workers collide more than they help. Beyond four, review load and cell-merge conflicts grow faster than throughput.

Rules:

- Spawn only for genuinely independent slices: separate activity sections, separate support scripts, separate docs, no shared notebook, no sequential dependency. A shared prerequisite (for example, installing dependencies or agreeing on a trace schema) MUST be resolved inline or split into sequenced waves.
- Prefer 2-3 subagents. Do the work in-session when it is a single cell edit, a prompt tweak, or needs conversation context the subagent cannot see.
- NEVER fan out for exploration that one or two reads can answer.
- Assign one integration owner per shared file. Sibling subagents MUST NOT edit the same `.ipynb`; when parallel work touches the notebook, each worker returns cell content and the owner applies it.
- Give every subagent its complete slice: target activity, expected trace shape, model/tool contract, and acceptance check (the section executes end-to-end and its trace is visible in Langfuse).
- Dispatch all independent tasks in one batch; NEVER spawn-wait-spawn.
- Collect results once. NEVER poll.
- A subagent MAY spawn its own workers only when its slice requires it; nested fan-out counts against the same cap of 4.
- Run notebook execution and smoke checks once after the wave, not per subagent. There is no test suite or linter to run.
- If a tool exposes a max-concurrency setting, set it to 4. If it does not, enforce the cap by dispatching in waves.

## Hackathon Scope and Boundaries

This repository is a one-time hackathon deliverable: a participant notebook that demonstrates LLM observability with Langfuse. It is not a product and not a library.

The repository exists to teach four investigative skills, in order: tracing a RAG pipeline with and without a retrieval filter, controlling output format, finding and fixing a hallucination via the system prompt, and debugging a broken tool call from trace data. Everything checked in MUST serve one of those four activities or the participant workflow around them.

Boundaries:

- The deliverable is the notebook participants clone and execute, plus the minimum support files it needs (dependency manifest, sample data, docs). Do not add application code, services, or deployment infrastructure.
- Langfuse is the observability backend. Do not build custom logging, dashboards, or telemetry plumbing that Langfuse already provides.
- Keep the exercises runnable by a participant on a laptop, in one sitting, against the repository's compose stack, with keys they create in the local Langfuse project. Docker and Docker Compose are prerequisites: the stack provides the Langfuse backend (postgres, clickhouse, redis, minio, langfuse web/worker) and the jupyter service. No cluster and no external database beyond that stack; inference is hosted outside it.
- Activity numbering, ordering, and the bugs planted in activities 3 and 4 are participant-facing contracts. Changing them changes the exercise; update the notebook, README, and mentor notes in the same change.
- Prefer boring, explicit notebook code over abstraction. A helper used in one activity stays inline in that activity.

Agenda:

| Activity | Topic | Duration | Participant outcome |
|---|---|---|---|
| 1 | RAG with and without filter | 35 min | Compare traces with and without retrieval filtering |
| 2 | Output format | 20 min | Compare traces for constrained vs unconstrained output |
| 3 | Fix hallucination | 20 min | Locate the hallucination in traces and fix the system prompt |
| 4 | Debug tool calling | 40 min | Diagnose a broken tool call from trace data and repair it |

Supporting agenda items: kickoff and notebook clone (15 min), breaks and mid-point progress check (10 min each), conclusion and wrap-up (20 min), team demos (30 min), voting and winners announcement (20 min), open exploration (10 min).

## Repository State

The repository is greenfield. Currently checked in: `LICENSE` (Apache-2.0) only. `.venv/` is a local Python 3.12 virtual environment used for host-side work; it is scratch, not a deliverable, and MUST NOT be committed.

Expected layout once the exercises exist:

```text
notebook.ipynb          participant notebook, one section per activity
docker-compose.yml      self-hosted Langfuse stack plus the jupyter service
Dockerfile              jupyter image build; installs requirements.txt
requirements.txt        dependency manifest (single source of pinned deps)
data/                   sample documents and fixtures used by the exercises
README.md               participant guide: setup, keys, activity walkthrough
```

`.env` carries compose and inference configuration; it is required for the stack and MUST NOT be committed.

Do not create directories speculatively. Add `data/` when the first exercise needs it.

## Dependencies

`requirements.txt` is the single pinned manifest; do not maintain a second dependency list. It MUST include `langfuse`, and notebooks MUST call the model through its OpenAI wrapper (`from langfuse.openai import OpenAI`) instead of the bare `openai` client, so generations are traced without hand-written instrumentation. The same manifest installs into `.venv` and into the jupyter image.

## Commands

Start the stack (Langfuse and jupyter) and validate its configuration:

```bash
docker compose config
docker compose up -d
```

Install dependencies into `.venv` for host-side work, never into the system interpreter:

```bash
.venv/bin/pip install -r requirements.txt
```

Run the participant notebook interactively, either inside the stack or on the host:

```bash
docker compose exec jupyter jupyter lab notebook.ipynb --ip=0.0.0.0
.venv/bin/jupyter lab notebook.ipynb
```

Execute the notebook headlessly to prove it still runs end-to-end:

```bash
docker compose exec jupyter jupyter nbconvert --to notebook --execute --inplace notebook.ipynb
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebook.ipynb
```

Langfuse credentials come from the environment; they are never written into cells. The stack is self-hosted, so the notebook reaches it at `http://langfuse:3000` from the jupyter container and at `http://localhost:3000` from the host:

```bash
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
export LANGFUSE_HOST=http://localhost:3000   # http://langfuse:3000 inside the compose network
```

Inference is hosted outside the stack. The notebook reads an OpenAI-compatible endpoint from the environment:

```bash
export OPENAI_BASE_URL=https://<provider>/v1
export OPENAI_API_KEY=...
export OPENAI_MODEL=...
```

If a `.env` file is used, it MUST stay uncommitted and be loaded explicitly — by `docker compose` for interpolation and by the host shell when running under `.venv` — so participants are not surprised by hidden state.

## Notebook Conventions

Match the existing style once cells exist. Do not reformat untouched sections.

- One top-level section per activity, numbered to match the agenda. Each section starts with a Markdown cell stating the goal, the expected observation, and the deliverable for that activity.
- Cells MUST execute top-to-bottom in a fresh kernel without manual reordering. Clear stale outputs before committing; the notebook ships executed, with outputs that show the comparison the activity asks for.
- Deterministic by default: fixed seeds, fixed prompts, fixed inputs. Where randomness is the point (sampling, temperature), say so in the cell and record the parameters in the trace.
- No secrets, absolute local paths, or machine-specific state in cells. Read configuration from the environment and fail loudly when a key is missing.
- Keep model and tool configuration in a small number of cells near the top of each section so participants can change one thing and observe the effect. Model configuration cells read `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` from the environment and fail loudly when any is missing.
- Print or display only what the activity asks participants to compare: the answer, the trace id or URL, token counts, cost, latency. Avoid dumping raw JSON.
- Planted defects in activities 3 and 4 MUST be visible in the trace, not hidden behind a comment that explains them. The participant finds the cause from observability data.

## Langfuse Tracing Conventions

The exercises are worthless if traces are uninformative. Every activity MUST produce a trace a participant can investigate:

- Name traces and spans by activity (for example `activity-1-rag-no-filter`, `activity-4-tool-call`), so participants and mentors can find them without guessing.
- Attach the prompts, retrieved documents, tool arguments, and tool results to the corresponding generation or span. A trace that only records latency cannot support activities 3 and 4.
- Instantiate the model client through `langfuse.openai` so every call is recorded as a generation with model, parameters, token usage, and cost; keep the wrapper active in every activity, including the deliberately broken ones. Mentors capture these numbers during the hackathon; do not compute them by hand when the SDK reports them.
- Use one Langfuse session per activity run and tag it with the activity number, so comparisons between variants stay grouped.
- Flush the client before the notebook ends; a missing flush loses the last traces and looks like a bug in the exercise.
- Never log secrets or full document corpora beyond what the activity needs.

## Verification

There is no test suite or linter. Verification is execution plus observation:

- A change to an activity is verified by executing the notebook section in a fresh kernel and confirming its trace appears in Langfuse with the spans the activity depends on.
- A change to prompts or model configuration is verified by comparing the before and after traces, not by reading the answer.
- A change to setup, dependencies, or credentials handling is verified by running the notebook from a clean environment with only the documented variables set.
- A change to the compose stack or jupyter image is verified with `docker compose config` and a full notebook execution inside the jupyter service.
- Activities 3 and 4 are verified by confirming the defect reproduces before the fix and disappears after it, with the trace showing the difference.
- CI, if added, runs notebook execution only; it cannot assert on trace content unless it talks to a Langfuse project.

## Documentation

`README.md` is the participant guide: setup, keys, activity order, what to look for in Langfuse, and how to submit findings. It MUST stay consistent with the notebook's section numbering and with this file's agenda table. Update it in the same change as any activity rename, reorder, or added prerequisite.

Mentor-facing notes, when they exist, live in the README or a single `MENTORS.md`; do not scatter run instructions across files.

## General Guidelines

1. Before writing any code, describe your approach. Wait for approval when the change is non-trivial or requirements are ambiguous; for a trivial single-file fix, proceed.
2. If requirements are ambiguous, ask clarifying questions before writing any code.
3. After writing any code, list runtime edge cases and suggest smoke checks: missing keys, stale kernel state, rate limits, trace flush, model availability.
4. If a task requires changes to more than 3 files, stop and break it into smaller tasks first.
5. When there is a bug, reproduce it first with a failing notebook execution or a failing trace inspection, then fix it until the reproduction passes.
6. Every time the user corrects you, reflect on what you did wrong and form a plan to never repeat that mistake.

## Behavioral Guidelines

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum change that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If a notebook section grows by 200 lines when 50 would do, rewrite it.

Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing files:
- Don't "improve" adjacent cells, comments, or formatting.
- Don't refactor activities that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead cells or stale outputs, mention it — don't delete it.

When your changes create orphans:
- Remove cells, fixtures, dependencies, and README steps that YOUR change made unused.
- Don't remove pre-existing unused content unless asked.

The test: every changed line traces directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add an activity" → "Execute the section in a fresh kernel and show the trace it produces in Langfuse."
- "Fix a hallucination" → "Reproduce the wrong answer, fix the system prompt, and show the corrected trace."
- "Fix tool calling" → "Reproduce the failing tool call, repair it, and show the successful tool span."
- "Change setup" → "Run the notebook from a clean environment with only the documented variables."

For multi-step tasks, state a brief plan:

```text
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.
