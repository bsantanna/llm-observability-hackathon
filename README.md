# LLM Observability Hackathon

An escape room for engineers who are new to LLMs. Skyline Travel's AI assistant, Skye, is having
a very bad day: a fisherman lost his fish, an influencer wants a selfie in the cockpit, a farmer
is flying with his rooster as an alarm clock, and an elderly lady would like to know where her
grand piano is. Four comic **Mini-Games**, one per story, each a chain of clues you solve by
reading the activity logs in Langfuse. Every answer opens the next door; every Mini-Game gives a
fragment of the code that opens the vault at the end.

The participant notebooks are `notebook-1-rag.ipynb`, `notebook-2-output-format.ipynb`,
`notebook-3-hallucination.ipynb`, and `notebook-4-tool-calling.ipynb`; each runs against the
local Langfuse stack and an OpenAI-compatible model endpoint. Game masters: see `MENTORS.md`.

## Prerequisites

- Docker and Docker Compose.
- An OpenAI-compatible chat-completions endpoint and a model name it serves. The model must
  support tool calling (Mini-Game 4 forces a tool call).
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

## Mini-Games

Each Mini-Game has its own session (`activity-<n>-<run-id>`) and tags (`activity-<n>`,
`l<level>`, `team-<your-team>`), so the runs stay grouped. Langfuse calls these records traces;
the notebooks call them activity logs. Open the activity-log link printed by the notebook and look
for the evidence there: the notebooks never print it. When a notebook runs inside the Docker
network, the link is rewritten so it opens from your browser.

| Mini-Game | Notebook | Story | Activity-log names | What to look at |
|---|---|---|---|---|
| 1 — Something Smells Fishy | `notebook-1-rag.ipynb` | A fisherman's lost bag of fresh-caught fish | `activity-1-rag-l<level>-<variant>` | The search step: its filter, how many items it returned, which ones, and what the answer cost. |
| 2 — The Cockpit Selfie | `notebook-2-output-format.ipynb` | An influencer who wants a selfie with the pilot | `activity-2-output-l<level>-<variant>` | The booking system's reason code, and one step per customer request. |
| 3 — Cock-a-Doodle-Don't | `notebook-3-hallucination.ipynb` | A farmer flying with his rooster as an alarm clock | `activity-3-hallucination-l<level>-<variant>` | The instructions in the answer step, the notice in the search step (including its status), and one step per farmer question. |
| 4 — The Piano Has Left the Building | `notebook-4-tool-calling.ipynb` | An elderly lady looking for her grand piano | `activity-4-tool-call-l<level>-<variant>` | The `get_booking` tool step: what was sent, what came back, errors, and the timing of its inner steps. |

## How to play

1. **Team name.** Put your team name in the first code cell of every notebook
   (`TEAM = "..."`) and use exactly the same name everywhere.
2. **Doors.** Every clue sits behind a door. Run its cell: an open door prints a briefing, a
   locked one prints 🔒 and a joke. The first clue of each Mini-Game is always open.
3. **Answers.** Find the answer in the activity log and type it into `check_flag("1-1", "...")`.
   Wrong guesses cost nothing. A correct answer opens the next door: rerun the next cell.
4. **Hints.** `hint("1-1")` gives a nudge and costs 10% of that clue's points (two at most).
   Still stuck after both hints? Ask the game master, who will give you the answer.
5. **Vault.** The last clue of each Mini-Game gives a 🔑 fragment. The four fragments, in order,
   open the vault at the end of Mini-Game 4. Teams may share fragments.
6. **Claim codes.** Each correct answer prints a claim code. Paste it into the game master's
   form. The scoreboard only decides the final tally; the screen shows a shared recovery meter.
7. **Helping.** If you have escaped a Mini-Game, help a stuck team by pointing at the right step
   (never the answer). The game master gives good-colleague points.
8. **Post-mortem.** At the end, each team explains the root cause of one Mini-Game with one
   before/after pair of activity logs.

Some clues ask you to change something (instructions, a search setting, a tool) and rerun.
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
- A door stays locked — run the previous clue's `check_flag` again with its answer. Progress is
  kept in `.game_state.json` per team name, so a changed `TEAM` starts with every door locked.
  Delete that file to start over.
- `TEAM is still 'your-team-name'` — set your team name in the first code cell and rerun it.
