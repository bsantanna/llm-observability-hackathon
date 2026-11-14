# LLM Observability Hackathon

Follow traces, compare model behavior, find a hallucination, and debug a broken
tool call. The participant notebooks are `notebook-1-rag.ipynb`,
`notebook-2-output-format.ipynb`, `notebook-3-hallucination.ipynb`, and
`notebook-4-tool-calling.ipynb`; each runs one activity against the repository's
self-hosted Langfuse stack and an OpenAI-compatible inference endpoint.

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
environment and fails loudly when a variable is missing:

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

Open each activity notebook in JupyterLab and execute the cells top-to-bottom in
a fresh kernel. The notebooks ship executed; rerunning one replaces its outputs
and creates new traces.

Headless execution:

```bash
docker compose exec jupyter jupyter nbconvert --to notebook --execute --inplace \
--ExecutePreprocessor.timeout=600 notebook-1-rag.ipynb notebook-2-output-format.ipynb \
notebook-3-hallucination.ipynb notebook-4-tool-calling.ipynb
.venv/bin/jupyter nbconvert --to notebook --execute --inplace \
--ExecutePreprocessor.timeout=600 notebook-1-rag.ipynb notebook-2-output-format.ipynb \
notebook-3-hallucination.ipynb notebook-4-tool-calling.ipynb
```

The timeout matters: reasoning models can take tens of seconds per call.

## Activities

Each activity uses its own Langfuse session (`activity-<n>-<run-id>`) and tags.
Open the trace URL printed by the notebook, then compare the variants. When a
notebook runs inside the compose network, it rewrites `langfuse:3000` URLs to
`http://localhost:3000` so they open from the host browser.

| Activity | Notebook | Trace names | What to look for |
|---|---|---|---|
| 1 — RAG with and without filter | `notebook-1-rag.ipynb` | `activity-1-rag-no-filter`, `activity-1-rag-filter` | The retriever span's `filter`, the retrieved document, and the answer. Compare the unfiltered and filtered runs. |
| 2 — Output format | `notebook-2-output-format.ipynb` | `activity-2-output-unconstrained`, `activity-2-output-constrained` | The generation output and the validation result. Compare what the downstream parser accepts. |
| 3 — Fix hallucination | `notebook-3-hallucination.ipynb` | `activity-3-hallucination-broken`, `activity-3-hallucination-fixed` | The generation input (system prompt) against the retriever output (policy document). Find the contradiction and fix the prompt. |
| 4 — Debug tool calling | `notebook-4-tool-calling.ipynb` | `activity-4-tool-call-broken`, `activity-4-tool-call-fixed` | The `get_booking` tool span: its arguments, level, and error. Compare the broken and fixed tool implementations. |

Hints, not solutions:

- Activity 3: the broken run's system message makes a claim that the retrieved
  policy does not support. The fixed run should follow the document.
- Activity 4: the tool span records the argument the model sent and the argument
  the implementation tried to read. Fix the implementation, not the prompt.

## Submit your findings

For each activity, submit:

- The trace URL.
- The retrieved document or tool arguments that explain the behavior.
- The root cause and the change you made (prompt or tool implementation).

For Activities 3 and 4, include both the broken and fixed trace URLs and state
what changed between them.

## Troubleshooting

- `RuntimeError: Missing environment variables` — export every variable listed in
  the error; the import stops before creating a client.
- `RuntimeError: Langfuse authentication failed` — check `LANGFUSE_BASE_URL`,
  `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY` against the project in Langfuse.
- Model calls are slow — lower the provider's reasoning budget if it exposes one;
  the notebooks bound `max_tokens` but cannot bound provider latency.
- Traces are missing — run the wrap-up cell in that notebook; it flushes the
  Langfuse client.
