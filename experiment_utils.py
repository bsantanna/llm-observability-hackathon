"""Shared setup for the LLM Observability Hackathon notebooks.

Importing this module validates the environment, creates the Langfuse and
OpenAI clients, loads the sample corpus, and exposes the trace helpers used
by every activity notebook.
"""

import json
import os
import uuid
from pathlib import Path

from langfuse import Langfuse, propagate_attributes
from langfuse.openai import OpenAI

REQUIRED = [
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
    "OPENAI_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
]
missing = [name for name in REQUIRED if not os.environ.get(name)]
if missing:
    raise RuntimeError("Missing environment variables: " + ", ".join(missing))

LANGFUSE_BASE_URL = os.environ["LANGFUSE_BASE_URL"]
MODEL = os.environ["OPENAI_MODEL"]
RUN_ID = uuid.uuid4().hex[:8]
TRACE_URLS = {}

langfuse = Langfuse()
try:
    authenticated = langfuse.auth_check()
except Exception as exc:
    raise RuntimeError(
        f"Langfuse authentication failed for {LANGFUSE_BASE_URL}: {exc}"
    ) from exc
if not authenticated:
    raise RuntimeError(f"Langfuse authentication failed for {LANGFUSE_BASE_URL}")

client = OpenAI(
    base_url=os.environ["OPENAI_BASE_URL"],
    api_key=os.environ["OPENAI_API_KEY"],
)

_CORPUS_PATH = Path(__file__).resolve().parent / "data" / "travel_corpus.json"
with _CORPUS_PATH.open(encoding="utf-8") as _corpus_file:
    CORPUS = json.load(_corpus_file)


def trace_url(trace_id):
    url = langfuse.get_trace_url(trace_id=trace_id) or trace_id
    return url.replace("://langfuse:3000", "://localhost:3000")


def show_trace(trace_id):
    url = trace_url(trace_id)
    print(f"trace: {url}")
    return url


def record_trace(name, trace_id):
    url = trace_url(trace_id)
    TRACE_URLS[name] = url
    return url


def retrieve(query, tier=None):
    documents = CORPUS["documents"]
    if tier is not None:
        documents = [doc for doc in documents if doc["tier"] == tier]
    terms = query.lower().split()
    ranked = sorted(
        ((sum(term in doc["text"].lower() for term in terms), index, doc)
         for index, doc in enumerate(documents)),
        key=lambda row: (-row[0], row[1]),
    )
    score, _, doc = ranked[0]
    return {
        "id": doc["id"],
        "tier": doc["tier"],
        "title": doc["title"],
        "text": doc["text"],
        "score": score,
    }


def print_summary(activity):
    print("run id:", RUN_ID)
    print(f"session activity-{activity}-{RUN_ID}")
    for name, url in TRACE_URLS.items():
        print(f"{name}: {url}")
