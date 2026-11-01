"""Sync state: which article version is in the vector store.

The vector store itself is the manifest: every file carries `source_url` and
`hash` attributes. A cloud cron job has an ephemeral disk, so a local manifest
file would be lost between runs and every run would re-upload everything.
Files uploaded before hashes existed have no `hash`, so they count as updated.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts"


@dataclass
class Entry:
    file_id: str
    hash: str | None


def load_manifest(client: OpenAI, store_id: str) -> dict[str, Entry]:
    manifest: dict[str, Entry] = {}
    for f in client.vector_stores.files.list(store_id, limit=100):
        attrs = f.attributes or {}
        url = attrs.get("source_url")
        if isinstance(url, str):
            h = attrs.get("hash")
            manifest[url] = Entry(f.id, h if isinstance(h, str) else None)
    return manifest


def save_run(summary: dict) -> Path:
    ARTIFACTS.mkdir(exist_ok=True)
    path = ARTIFACTS / "latest-run.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return path
