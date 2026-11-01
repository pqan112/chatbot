import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openai import OpenAI

from ..storage.manifest import Entry

WORKERS = 5

# Static chunking, same values as OpenAI's default "auto", set explicitly.
CHUNKING = {
    "type": "static",
    "static": {"max_chunk_size_tokens": 800, "chunk_overlap_tokens": 400},
}

log = logging.getLogger("job")


def ensure_store(client: OpenAI, store_id: str) -> str:
    if store_id:
        return store_id
    store_id = client.vector_stores.create(name="optibot-docs").id
    log.info("created vector store %s <- set VECTOR_STORE_ID", store_id)
    return store_id


def upload(
    client: OpenAI,
    store_id: str,
    items: list[dict],
    manifest: dict[str, Entry],
) -> tuple[int, int]:
    """Upload records (path, source_url, title, updated, hash). Returns (uploaded, failed).

    The stale file of an updated article is deleted first.
    """
    if not items:
        return 0, 0
    for a in items:
        old = manifest.get(a["source_url"])
        if old:
            client.vector_stores.files.delete(old.file_id, vector_store_id=store_id)

    def put(a: dict) -> dict:
        with Path(a["path"]).open("rb") as fh:
            file_id = client.files.create(file=fh, purpose="assistants").id
        attrs = {k: a[k] for k in ("source_url", "title", "updated", "hash")}
        return {"file_id": file_id, "attributes": attrs}

    with ThreadPoolExecutor(WORKERS) as pool:
        entries = list(pool.map(put, items))
    batch = client.vector_stores.file_batches.create_and_poll(
        store_id, files=entries, chunking_strategy=CHUNKING
    )
    failed = batch.file_counts.failed
    return len(items) - failed, failed
