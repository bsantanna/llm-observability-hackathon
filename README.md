# LLM Observability Hackathon

Follow the activity logs, compare how the assistant behaves, correct a wrong answer,
and fix a failed lookup. The participant notebooks are `notebook-1-rag.ipynb`,
`notebook-2-output-format.ipynb`, `notebook-3-hallucination.ipynb`, and
`notebook-4-tool-calling.ipynb`; each walks through one activity against the local
Langfuse stack and an OpenAI-compatible model endpoint.

## Prerequisites

- Docker and Docker Compose.
- An OpenAI-compatible chat-completions endpoint and a model name it serves.
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
a new kernel. The notebooks come with example outputs; running one again replaces
its outputs and creates new activity logs.

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

Each activity has its own session (`activity-<n>-<run-id>`) and tags, so the runs
stay grouped. Langfuse calls these records traces; this guide calls them activity
logs. Open the activity-log link printed by the notebook, then compare the runs.
When a notebook runs inside the Docker network, the link is rewritten so it opens
from your browser.

| Activity | Notebook | Activity-log names | What to look for |
|---|---|---|---|
| 1 — Searching the right policy | `notebook-1-rag.ipynb` | `activity-1-rag-no-filter`, `activity-1-rag-filter` | The search filter, the policy the assistant found, and the answer. Compare the two runs. |
| 2 — Getting a usable answer | `notebook-2-output-format.ipynb` | `activity-2-output-unconstrained`, `activity-2-output-constrained` | The assistant's answer and the format check. Compare which answer the next system can use. |
| 3 — Correcting a wrong answer | `notebook-3-hallucination.ipynb` | `activity-3-hallucination-broken`, `activity-3-hallucination-fixed` | The instructions given to the assistant and the policy it found. Find the contradiction and correct the instructions. |
| 4 — Fixing a failed lookup | `notebook-4-tool-calling.ipynb` | `activity-4-tool-call-broken`, `activity-4-tool-call-fixed` | The `get_booking` tool step: the details sent, the status, and the error. Compare the two runs. |

Hints, not solutions:

- Activity 3: the first run's instructions say something the policy does not
  support. The corrected run should follow the policy.
- Activity 4: the tool step records the detail the assistant sent and the detail
  the tool tried to read. Correct the tool, not the assistant's wording.

## Submit your findings

For each activity, submit:

- The activity-log link.
- The policy or tool details that explain the behavior.
- The cause and the change you made (instructions or tool).

For Activities 3 and 4, include both activity-log links and state what changed
between them.

## Troubleshooting

- `RuntimeError: Missing environment variables` — export every variable listed in
  the error; the import stops before creating a client.
- `RuntimeError: Langfuse authentication failed` — check `LANGFUSE_BASE_URL`,
  `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY` against the project in Langfuse.
- The assistant is slow — lower the provider's reasoning setting if it exposes
  one; the notebooks limit the answer length but cannot make the provider faster.
- Activity logs are missing — run the wrap-up cell in that notebook; it sends the
  remaining activity logs to Langfuse.
