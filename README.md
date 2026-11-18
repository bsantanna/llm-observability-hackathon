# LLM Observability Hackathon

Follow the activity logs, compare how the assistant behaves, correct a wrong answer,
and fix a failed lookup, played as a game: three levels per case, flags, hints and a
scoreboard. The participant notebooks are `notebook-1-rag.ipynb`,
`notebook-2-output-format.ipynb`, `notebook-3-hallucination.ipynb`, and
`notebook-4-tool-calling.ipynb`; each walks through one case against the local
Langfuse stack and an OpenAI-compatible model endpoint. Game masters: see `MENTORS.md`.

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

Four cases, each with three levels that get harder. Each case has its own session
(`activity-<n>-<run-id>`) and tags (`activity-<n>`, `l<level>`, `team-<your-team>`), so the
runs stay grouped. Langfuse calls these records traces; this guide calls them activity logs.
Open the activity-log link printed by the notebook and look for the evidence there: the
notebooks never print it. When a notebook runs inside the Docker network, the link is
rewritten so it opens from your browser.

| Case | Notebook | Activity-log names | What to look at |
|---|---|---|---|
| 1 — Searching the right policy | `notebook-1-rag.ipynb` | `activity-1-rag-l<level>-<variant>` | The search step: its limits, how many policies it returned, which ones, and what the answer cost. |
| 2 — Getting a usable answer | `notebook-2-output-format.ipynb` | `activity-2-output-l<level>-<variant>` | The instructions, the booking system's check and reason code, and one step per customer request. |
| 3 — Correcting a wrong answer | `notebook-3-hallucination.ipynb` | `activity-3-hallucination-l<level>-<variant>` | The instructions in the answer step, the policy in the search step (including its status), and one step per rule-check question. |
| 4 — Fixing a failed lookup | `notebook-4-tool-calling.ipynb` | `activity-4-tool-call-l<level>-<variant>` | The `get_booking` tool step: what was sent, what came back, errors, and the timing of its inner steps. |

## How the game works

1. **Team name.** Put your team name in the first code cell of every notebook
   (`TEAM = "..."`) and use exactly the same name everywhere.
2. **Levels.** Every case has Level 1 (100 points), Level 2 (200) and Level 3 (300). Each
   level asks you to find something in the activity logs.
3. **Flags.** Type what you found into `check_flag("2-1", "...")`. Wrong guesses cost
   nothing. A correct answer prints a **claim code**.
4. **Claim codes.** Paste each claim code into the form your game master shares. The
   scoreboard updates from the form.
5. **Hints.** `hint("2-1")` shows a hint. Each hint costs 25% of that level's points (two
   hints at most per level). The claim code already knows how many hints you used.
6. **Bonus.** One hidden flag is worth 150 points. The game master may drop a clue.
7. **Demo.** At the end, each team shows one before/after pair of activity logs. The final
   ranking combines flag points (60%) and the demo (40%).

Some levels ask you to change something (instructions, a search setting, a tool) and rerun.
Notebook cells are yours to edit: run the cells from top to bottom first, then experiment.

## Troubleshooting

- `RuntimeError: Missing environment variables` — export every variable listed in
  the error; the import stops before creating a client.
- `RuntimeError: Langfuse authentication failed` — check `LANGFUSE_BASE_URL`,
  `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY` against the project in Langfuse.
- The assistant is slow — lower the provider's reasoning setting if it exposes
  one; the notebooks limit the answer length but cannot make the provider faster.
- Activity logs are missing — run the wrap-up cell in that notebook; it sends the
  remaining activity logs to Langfuse.
- A claim code is not accepted by the form — check that `TEAM` is spelled the same in every
  notebook, rerun that cell, and run `check_flag` again.
- `TEAM is still 'your-team-name'` — set your team name in the first code cell and rerun it.
