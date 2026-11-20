# LLM Observability Hackathon

A hands-on Langfuse tutorial for engineers who are new to LLMs. Skyline Travel's AI assistant,
Skye, is having a very bad day: a fisherman lost his fish, an influencer wants a selfie in the
cockpit, a farmer is flying with his rooster as an alarm clock, and an elderly lady would like to
know where her grand piano is. Four comic activities, one per story. Each is a series of
**missions** you solve in Langfuse: read the trace, point at the step that went wrong, and fix
Skye's prompt and settings in Langfuse Prompt Management.

The participant notebooks are `notebook-1-rag.ipynb`, `notebook-2-output-format.ipynb`,
`notebook-3-hallucination.ipynb`, and `notebook-4-tool-calling.ipynb`; each runs against the
local Langfuse stack and an OpenAI-compatible model endpoint. Game masters: see `MENTORS.md`.

## Prerequisites

- Docker and Docker Compose.
- An OpenAI-compatible chat-completions endpoint and a model name it serves. The model must
  support tool calling (Activity 4 forces a tool call).
- Ports `3000` (Langfuse), `8888` (JupyterLab), and the compose stack's internal
  ports free on your machine.

## Start the stack

```bash
cp .env.example .env   # optional; edit the values you need
docker compose up -d
```

The stack seeds a Langfuse organization and project. The default project keys are
`pk-lf-hackathon` / `sk-lf-hackathon`; override them with
`LANGFUSE_INIT_PROJECT_PUBLIC_KEY` and `LANGFUSE_INIT_PROJECT_SECRET_KEY` in
`.env`. The stack also seeds a mentor login: `mentor@example.com` / `hackathon`.

Open Langfuse at <http://localhost:3000> and JupyterLab at
<http://localhost:8888>. The Jupyter token is `JUPYTER_TOKEN` from `.env`
(default `hackathon`).

## Configure the notebooks

The notebooks import `experiment_utils.py`, which reads configuration from the
environment and stops with a clear error when a value is missing:

```bash
export LANGFUSE_PUBLIC_KEY=pk-lf-hackathon
export LANGFUSE_SECRET_KEY=sk-lf-hackathon
export LANGFUSE_BASE_URL=http://localhost:3000   # http://langfuse:3000 inside compose
export OPENAI_BASE_URL=https://<provider>/v1
export OPENAI_API_KEY=<your-key>
export OPENAI_MODEL=<model-name>
```

The `jupyter` service receives the Langfuse keys and `OPENAI_*` values from the
compose environment. When running on the host under `.venv`, export the variables
yourself; the notebooks do not load `.env` implicitly.

## Run the notebooks

Open each activity notebook in JupyterLab and run the cells from top to bottom in
a new kernel. The notebooks ship without outputs; every run creates new traces in
your Langfuse.

Headless execution:

```bash
docker compose exec jupyter jupyter nbconvert --to notebook --execute --inplace \
--ExecutePreprocessor.timeout=600 notebook-1-rag.ipynb notebook-2-output-format.ipynb \
notebook-3-hallucination.ipynb notebook-4-tool-calling.ipynb
.venv/bin/jupyter nbconvert --to notebook --execute --inplace \
--ExecutePreprocessor.timeout=600 notebook-1-rag.ipynb notebook-2-output-format.ipynb \
notebook-3-hallucination.ipynb notebook-4-tool-calling.ipynb
```

Some model calls take tens of seconds.

## Activities

Each activity has its own session (`activity-<n>-<run-id>`) and tag (`activity-<n>`). The
notebook prints only a status line and a 📎 link to the trace: everything you need is in Langfuse.
Skye's instructions and settings are prompts in Langfuse (**Prompts** page); Skye always runs the
version with the `production` label.

| Activity | Notebook | Story | Prompt | Missions |
|---|---|---|---|---|
| 1 — Something Smells Fishy | `notebook-1-rag.ipynb` | A fisherman's lost bag of fresh-caught fish | `skye-lost-and-found` | 1.1–1.4: the trace tree, the search step, prompt config and versions, sessions and cost |
| 2 — The Cockpit Selfie | `notebook-2-output-format.ipynb` | An influencer who wants a selfie with the pilot | `skye-booking-format` | 2.1–2.2: a downstream rejection, iterating on a prompt |
| 3 — Cock-a-Doodle-Don't | `notebook-3-hallucination.ipynb` | A farmer flying with his rooster as an alarm clock | `skye-animals` | 3.1–3.2: the prompt behind an answer, stale data in the search |
| 4 — The Piano Has Left the Building | `notebook-4-tool-calling.ipynb` | An elderly lady looking for her grand piano | `skye-piano` | 4.1–4.3: tool errors, scoring a wrong result, the timeline |

## How to play

1. **Run** a mission cell. It prints one line and a 📎 link.
2. **Investigate** in Langfuse, following the mission's "In Langfuse" steps.
3. **Act** in Langfuse: comment on the step that went wrong, score it, or save a new prompt
   version with the `production` label. One fix (4.3) is a line of notebook code.
4. **Check**: run `check("1.2")`. ✅ means done; ❌ tells you what is still missing.
5. **Stuck?** Open the "💡 Stuck?" block under the mission, then ask the game master.

Cells can run in any order, as often as you like. `report()` lists your missions. Langfuse login:
`mentor@example.com` / `hackathon`. At the end, each team demos one activity with a before/after
pair of traces.

## Troubleshooting

- `RuntimeError: Missing environment variables` — export every variable listed in
  the error; the import stops before creating a client.
- `RuntimeError: Langfuse authentication failed` — check `LANGFUSE_BASE_URL`,
  `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY` against the project in Langfuse.
- `⚙️ Skye could not finish this run (AuthenticationError)` although `.env` has the right key —
  your shell exports its own `OPENAI_API_KEY`, and Docker Compose prefers shell variables over
  `.env`. Restart Jupyter without it: `env -u OPENAI_API_KEY docker compose up -d jupyter`.
- The assistant is slow — lower the provider's reasoning setting if it exposes
  one; the notebooks limit the answer length but cannot make the provider faster.
- `check` says there is no activity log yet — run the mission cell first, or wait a few seconds
  and run the check again.
- You changed a prompt but nothing changed — the new version needs the `production` label.
- `⚙️ Config of ...` — the prompt's config has a wrong value (for example `"true"` in quotes
  instead of `true`); save a new version with the value fixed.
- Start a prompt over — on the Prompts page, put the `production` label back on version 1.
