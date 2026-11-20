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

Rationale: the hackathon notebooks are shared files, so parallel workers collide more than they help. Beyond four, review load and cell-merge conflicts grow faster than throughput.

Rules:

- Spawn only for genuinely independent slices: separate activity notebooks, separate support scripts, separate docs, no shared notebook, no sequential dependency. A shared prerequisite (for example, installing dependencies or agreeing on a trace schema) MUST be resolved inline or split into sequenced waves.
- Prefer 2-3 subagents. Do the work in-session when it is a single cell edit, a prompt tweak, or needs conversation context the subagent cannot see.
- NEVER fan out for exploration that one or two reads can answer.
- Assign one integration owner per shared file. Sibling subagents MUST NOT edit the same `.ipynb`; when parallel work touches a notebook, each worker returns cell content and the owner applies it.
- Give every subagent its complete slice: target activity, expected trace shape, model/tool contract, and acceptance check (the notebook executes end-to-end and its trace is visible in Langfuse).
- Dispatch all independent tasks in one batch; NEVER spawn-wait-spawn.
- Collect results once. NEVER poll.
- A subagent MAY spawn its own workers only when its slice requires it; nested fan-out counts against the same cap of 4.
- Run notebook execution and smoke checks once after the wave, not per subagent. There is no test suite or linter to run.
- If a tool exposes a max-concurrency setting, set it to 4. If it does not, enforce the cap by dispatching in waves.

## Hackathon Scope and Boundaries

This repository is a one-time hackathon deliverable: participant notebooks that demonstrate LLM observability with Langfuse. It is not a product and not a library.

The repository exists to teach four investigative skills, in order: tracing a RAG pipeline with and without a retrieval filter, controlling output format, finding and fixing a hallucination via the system prompt, and debugging a broken tool call from trace data. Everything checked in MUST serve one of those four activities or the participant workflow around them. The activities are four comic, absurd stories set at the fictional Skyline Travel (a fisherman's lost fish, an influencer's cockpit selfie, a farmer's rooster, an elderly lady's grand piano); there are no ticket classes, loyalty levels or policy-rule puzzles.

Boundaries:

- The deliverable is the notebooks participants clone and execute, plus the minimum support files they need (dependency manifest, sample data, docs). Do not add application code, services, or deployment infrastructure.
- Langfuse is the observability backend. Do not build custom logging, dashboards, or telemetry plumbing that Langfuse already provides.
- Keep the exercises runnable by a participant on a laptop, in one sitting, against the repository's compose stack, with keys they create in the local Langfuse project. Docker and Docker Compose are prerequisites: the stack provides the Langfuse backend (postgres, clickhouse, redis, minio, langfuse web/worker) and the jupyter service. No cluster and no external database beyond that stack; inference is hosted outside it.
- Activity numbering, ordering, the missions per activity, their planted defects, the seeded prompts (names, version-1 text and config) and the observation names the checks look for are participant-facing contracts. Changing them changes the game; update the notebooks, `experiment_utils.py`, README, and `MENTORS.md` in the same change.
- The activities are played as **Langfuse missions**, a guided tutorial. A run cell runs Skye and prints only a status line and a trace link; the participant follows the mission's "In Langfuse" steps, then acts in Langfuse: a comment on the guilty step or trace, a `correct` score on a step, or a new `production` version of one of Skye's prompts (text and config live in Langfuse Prompt Management). `check("<mission>")` asks the Langfuse API whether the action is done and prints ✅ or a nudge; `report()` lists the missions. There are no typed answers, locks, points or claim codes; progress is shared, not ranked. Checks MUST rely only on code-controlled data (observation names, where a comment or score sits, facts the run code records on the trace) and never on comment text, model wording or token counts, except the code-checked outputs of missions 2.2 and 3.2.
- Never name an employer, a real event, its date, or a meeting platform anywhere in the repository. The only story is the fictional Skyline Travel.
- Prefer boring, explicit code over abstraction. Reusable activity logic lives in `experiment_utils.py`; notebooks call it and focus on the activity logs. A one-off display helper can stay inline.

Agenda:

| Activity | Topic | Duration | Participant outcome |
|---|---|---|---|
| 1 | Something Smells Fishy (search, RAG) | 35 min | Read a trace; comment on the search that let the rooster in; fix the filter and the number of results in the prompt config; find the expensive trace in a session |
| 2 | The Cockpit Selfie (output format) | 20 min | Comment on the booking system's rejection; write a prompt version that makes three messy requests usable |
| 3 | Cock-a-Doodle-Don't (wrong answers) | 20 min | Follow the answer to its prompt and remove a hidden instruction; comment on the search that served a retired notice and switch to current notices |
| 4 | The Piano Has Left the Building (tool calling) | 40 min | Comment on a failing tool call, score a wrong tool result, fix a cache that never hits; finish the report |

Supporting agenda items: kickoff and notebook clone (15 min), breaks and mid-point progress check (10 min each), conclusion and wrap-up (20 min), team demos (30 min), voting and winners announcement (20 min), open exploration (10 min).

## Repository State

The repository contains the compose stack, dependency manifest, sample data, shared notebook setup, and four participant notebooks. Currently checked in: `LICENSE` (Apache-2.0), `AGENTS.md`, `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `MENTORS.md`, `data/`, `experiment_utils.py`, the four `notebook-*.ipynb` files, and the design and plan under `docs/superpowers/`. `.venv/` is a local Python 3.12 virtual environment used for host-side work; it is scratch, not a deliverable, and MUST NOT be committed.

Layout:

```text
notebook-1-rag.ipynb    Activity 1: searching the right policy
notebook-2-output-format.ipynb  Activity 2: getting a usable answer
notebook-3-hallucination.ipynb  Activity 3: correcting a wrong answer
notebook-4-tool-calling.ipynb   Activity 4: fixing a failed lookup
experiment_utils.py     shared setup, prompt seeding, activity runs, mission checks
MENTORS.md              game master guide: run of show, mission answers, resets
docker-compose.yml      self-hosted Langfuse stack plus the jupyter service
Dockerfile              jupyter image build; installs requirements.txt
requirements.txt        dependency manifest (single source of pinned deps)
data/                   sample documents and fixtures used by the exercises
.env.example            documented template for uncommitted .env overrides
README.md               participant guide: setup, keys, activity walkthrough
```

`.env` carries inference and compose overrides; it MUST NOT be committed. `.env.example` documents the variables participants normally set.

Do not create directories speculatively. Add `data/` when the first exercise needs it.

## Dependencies

`requirements.txt` is the single pinned manifest; do not maintain a second dependency list. It MUST include `langfuse`, and the shared setup in `experiment_utils.py` MUST create the model client through `from langfuse.openai import OpenAI` instead of the bare `openai` client, so generations are traced without hand-written instrumentation. The same manifest installs into `.venv` and into the jupyter image.

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

Run the participant notebooks interactively. The jupyter service serves JupyterLab at `http://localhost:8888` with the token from `JUPYTER_TOKEN`; host-side runs use the local environment:

```bash
.venv/bin/jupyter lab notebook-1-rag.ipynb
```

Execute the notebooks headlessly to prove they still run end-to-end:

```bash
docker compose exec jupyter jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 notebook-1-rag.ipynb notebook-2-output-format.ipynb notebook-3-hallucination.ipynb notebook-4-tool-calling.ipynb
.venv/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 notebook-1-rag.ipynb notebook-2-output-format.ipynb notebook-3-hallucination.ipynb notebook-4-tool-calling.ipynb
```

Langfuse credentials come from the environment; they are never written into cells. The stack is self-hosted and seeds a project with `LANGFUSE_INIT_PROJECT_PUBLIC_KEY` / `LANGFUSE_INIT_PROJECT_SECRET_KEY`; the notebooks reach it at `http://langfuse:3000` from the jupyter container and at `http://localhost:3000` from the host:

```bash
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
export LANGFUSE_BASE_URL=http://localhost:3000   # http://langfuse:3000 inside the compose network
```

Inference is hosted outside the stack. The notebooks read an OpenAI-compatible endpoint from the environment:

```bash
export OPENAI_BASE_URL=https://<provider>/v1
export OPENAI_API_KEY=...
export OPENAI_MODEL=...
```

If a `.env` file is used, it MUST stay uncommitted. `docker compose` reads it for interpolation; when running under `.venv` on the host, source it explicitly — so participants are not surprised by hidden state.

## Notebook Conventions

Match the existing style once cells exist. Do not reformat untouched sections.

- One notebook per activity, numbered to match the agenda. Each notebook starts with a Markdown cell stating the purpose, the expected observation, the bad practice, the good practice, why the good practice works, and the deliverable for that activity.
- Write for engineers new to LLMs: plain language, light and absurd humor (the joke is the situation, never the person), and explain technical terms (trace/activity log, span/step, generation/answer) the first time they appear.
- Cells MUST execute top-to-bottom in a fresh kernel without manual reordering. Notebooks ship with cleared outputs: links would point to traces that do not exist in a participant's stack.
- Deterministic by default: fixed seeds, fixed prompts, fixed inputs. Where randomness is the point (sampling, temperature), say so in the cell and record the parameters in the trace.
- No secrets, absolute local paths, or machine-specific state in cells. Read configuration from the environment and fail loudly when a key is missing.
- Model, client, and activity logic live in `experiment_utils.py`; notebooks call it and focus on the activity logs. The shared setup reads `LANGFUSE_*` and `OPENAI_*` from the environment and stops with a clear error when a value is missing.
- A run prints one status line and the trace link, nothing else: never the answer, ids, tokens, cost, latency, prompt text or verdicts. Everything to compare lives in Langfuse.
- Planted defects in every level MUST be visible in the trace, not hidden behind a comment that explains them. The participant finds the cause from observability data.
- Each mission is: Markdown briefing with numbered "In Langfuse" steps, a run cell (when needed), a collapsed "💡 Stuck?" block, and a `check("<mission>")` cell. No cell raises because a mission is not done or a prompt config is malformed.
- Answers and fixes live in plain text in `MENTORS.md`. `experiment_utils.py` seeds Skye's prompts at import only when missing and never overwrites a team's edits.

## Langfuse Tracing Conventions

The exercises are worthless if traces are uninformative. Every activity MUST produce a trace a participant can investigate:

- Name traces and spans by activity (for example `activity-1-rag-no-filter`, `activity-4-tool-call`), so participants and mentors can find them without guessing.
- Attach the prompts, retrieved documents, tool arguments, and tool results to the corresponding generation or span. A trace that only records latency cannot support activities 3 and 4.
- The shared setup in `experiment_utils.py` instantiates the model client through `langfuse.openai` so every call is recorded as a generation with model, parameters, token usage, and cost; keep the wrapper active in every activity, including the deliberately broken ones. Mentors capture these numbers during the hackathon; do not compute them by hand when the SDK reports them.
- Use one Langfuse session per activity run and tag it with the activity number, so comparisons between variants stay grouped.
- Flush the client before each notebook ends; a missing flush loses the last traces and looks like a bug in the exercise.
- Never log secrets or full document corpora beyond what the activity needs.

## Verification

There is no test suite or linter. Verification is execution plus observation:

- A change to an activity is verified by executing that activity's notebook in a fresh kernel and confirming its trace appears in Langfuse with the spans the activity depends on.
- A change to prompts or model configuration is verified by comparing the before and after traces, not by reading the answer.
- A change to setup, dependencies, or credentials handling is verified by running any notebook from a clean environment with only the documented variables set.
- A change to the compose stack or jupyter image is verified with `docker compose config` and a full notebook execution inside the jupyter service.
- Every mission is verified by doing its Langfuse action and seeing its check turn ✅; missions with a fix are verified by confirming the defect reproduces before the fix and disappears after it, with the trace showing the difference.
- CI, if added, runs notebook execution only; it cannot assert on trace content unless it talks to a Langfuse project.

## Documentation

`README.md` is the participant guide: setup, keys, activity order, what to look for in Langfuse, and how the missions and checks work. It MUST stay consistent with the notebooks' activity numbering and with this file's agenda table. Update it in the same change as any activity rename, reorder, or added prerequisite.

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
- If an activity notebook grows by 200 lines when 50 would do, rewrite it.

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
- "Add an activity" → "Execute the activity notebook in a fresh kernel and show the trace it produces in Langfuse."
- "Fix a hallucination" → "Reproduce the wrong answer, fix the system prompt, and show the corrected trace."
- "Fix tool calling" → "Reproduce the failing tool call, repair it, and show the successful tool span."
- "Change setup" → "Run any notebook from a clean environment with only the documented variables."

For multi-step tasks, state a brief plan:

```text
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.
