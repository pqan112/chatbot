"""Daily job: re-scrape help-center articles, upload only the delta, log counts.

Run: python -m app.main   (exit 0 on success, 1 on any failure)
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from .config import settings
from .ingestion.compare_articles import compare
from .ingestion.hash_utils import sha256
from .ingestion.upload_to_vector_store import ensure_store, upload
from .scraper.convert_to_markdown import slugify, to_markdown
from .scraper.fetch_articles import fetch_articles
from .storage.manifest import load_manifest, save_run

ARTICLES = Path(__file__).resolve().parent.parent / "data" / "articles"

log = logging.getLogger("job")


def scrape(limit: int | None) -> list[dict]:
    """Fetch, convert, write markdown when content changed. Returns per-article records."""
    ARTICLES.mkdir(parents=True, exist_ok=True)
    records = []
    articles = fetch_articles(limit)
    log.info("fetched %d published articles from Zendesk", len(articles))
    for a in articles:
        text = to_markdown(a)
        path = ARTICLES / f"{slugify(a['title'])}-{a['id']}.md"
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
        records.append(
            {
                "path": str(path),
                "source_url": a["html_url"],
                "title": a["title"],
                "updated": a["updated_at"],
                "hash": sha256(text),
            }
        )
    return records


def run(limit: int | None) -> dict:
    client = OpenAI(api_key=settings.openai_api_key)
    store_id = ensure_store(client, settings.vector_store_id)
    scraped = scrape(limit)
    manifest = load_manifest(client, store_id)
    log.info("vector store %s holds %d files", store_id, len(manifest))
    delta = compare(scraped, manifest)
    log.info(
        "delta: added=%d updated=%d skipped=%d",
        len(delta.added),
        len(delta.updated),
        len(delta.skipped),
    )
    uploaded, failed = upload(client, store_id, delta.added + delta.updated, manifest)
    return {
        "scraped": len(scraped),
        "added": len(delta.added),
        "updated": len(delta.updated),
        "skipped": len(delta.skipped),
        "uploaded": uploaded,
        "failed": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily Chatbot knowledge-base sync")
    parser.add_argument("-n", "--limit", type=int, help="max articles (default: all)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    summary: dict = dict.fromkeys(
        ("scraped", "added", "updated", "skipped", "uploaded", "failed"), 0
    )
    error = None
    try:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        summary = run(args.limit)
    except Exception as e:
        log.exception("job failed")
        error = str(e)
    ok = error is None and summary["failed"] == 0
    summary |= {
        "status": "SUCCESS" if ok else "FAILED",
        "started": started.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "duration_seconds": round(time.monotonic() - t0, 1),
        "error": error,
    }
    save_run(summary)
    bar = "=" * 40
    log.info(
        "%s\nChatbot Knowledge Base Sync\n%s\nStarted: %s\n\n"
        "Total articles scraped: %d\n\nAdded:   %d\nUpdated: %d\nSkipped: %d\n\n"
        "Uploaded: %d\nFailed:   %d\n\nStatus: %s\nDuration: %.1f seconds\n%s",
        bar,
        bar,
        summary["started"],
        summary["scraped"],
        summary["added"],
        summary["updated"],
        summary["skipped"],
        summary["uploaded"],
        summary["failed"],
        summary["status"],
        summary["duration_seconds"],
        bar,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
