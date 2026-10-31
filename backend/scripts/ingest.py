"""Chunk data/articles/*.md, embed with Ollama, store in Neon pgvector.

Run from backend/: python -m scripts.ingest
"""

import re
from pathlib import Path

import psycopg
from psycopg import sql
from openai import OpenAI
from pgvector.psycopg import register_vector

from app.config import settings

ARTICLES = Path(__file__).resolve().parent.parent / "data" / "articles"
EMBED_DIM = 768  # nomic-embed-text
DOC_PREFIX = "search_document: "  # nomic-embed-text; queries use "search_query: "
MERGE_TO = 1000
MAX_CHUNK = 1500
OVERLAP = 150
BATCH = 32

IMG_LINE = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$", re.MULTILINE)
HEADING = re.compile(r"^###\s+(.*)$", re.MULTILINE)

SCHEMA = sql.SQL("""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunks (
    id bigserial PRIMARY KEY,
    source_url text NOT NULL,
    title text NOT NULL,
    heading text NOT NULL,
    chunk_index int NOT NULL,
    content text NOT NULL,
    article_updated text NOT NULL,
    embedding vector({dim}) NOT NULL,
    UNIQUE (source_url, chunk_index)
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
""").format(dim=sql.Literal(EMBED_DIM))


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    title = re.search(r"^#\s+(.*)$", text, re.MULTILINE)
    source = re.search(r"^Source:\s*(\S+)", text, re.MULTILINE)
    updated = re.search(r"^Updated:\s*(\S+)", text, re.MULTILINE)
    if not (title and source and updated):
        raise ValueError(f"{path.name}: missing title/Source/Updated")
    body = text[updated.end():]
    return {
        "title": title.group(1).strip(),
        "source": source.group(1),
        "updated": updated.group(1),
        "body": IMG_LINE.sub("", body).strip(),
    }


def sections(body: str) -> list[tuple[str, str]]:
    """Split on ### headings -> [(heading, text)]. Intro before first heading has heading ''."""
    parts = HEADING.split(body)  # [intro, h1, t1, h2, t2, ...]
    out = [("", parts[0].strip())]
    for i in range(1, len(parts), 2):
        out.append((parts[i].strip(" *"), parts[i + 1].strip()))
    return [(h, t) for h, t in out if t]


def split_long(text: str) -> list[str]:
    """Pack paragraphs up to MAX_CHUNK; carry OVERLAP chars into the next piece."""
    pieces, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        if cur and len(cur) + len(para) + 2 > MAX_CHUNK:
            pieces.append(cur)
            cur = cur[-OVERLAP:] + "\n\n" + para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
        while len(cur) > MAX_CHUNK:  # single oversize paragraph
            pieces.append(cur[:MAX_CHUNK])
            cur = cur[MAX_CHUNK - OVERLAP:]
    if cur:
        pieces.append(cur)
    return pieces


def chunk(article: dict) -> list[tuple[str, str]]:
    """-> [(heading, content)]; small sections merged up to MERGE_TO."""
    merged: list[tuple[str, str]] = []
    for heading, text in sections(article["body"]):
        block = f"### {heading}\n{text}" if heading else text
        if merged and len(merged[-1][1]) + len(block) + 2 <= MERGE_TO:
            merged[-1] = (merged[-1][0] or heading, f"{merged[-1][1]}\n\n{block}")
        else:
            merged.append((heading, block))
    out = []
    for heading, block in merged:
        for piece in split_long(block) if len(block) > MAX_CHUNK else [block]:
            out.append((heading, piece))
    return out


def embed(client: OpenAI, texts: list[str]) -> list[list[float]]:
    vectors = []
    for i in range(0, len(texts), BATCH):
        res = client.embeddings.create(
            model=settings.embed_model, input=texts[i : i + BATCH]
        )
        vectors.extend(d.embedding for d in res.data)
    return vectors


def main() -> None:
    if not settings.neon_database_url:
        raise SystemExit("NEON_DATABASE_URL not set in backend/.env")
    client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)

    with psycopg.connect(settings.neon_database_url, autocommit=True) as conn:
        conn.execute(SCHEMA)
        register_vector(conn)
        files = sorted(ARTICLES.glob("*.md"))
        done = skipped = total = 0
        for n, path in enumerate(files, 1):
            art = parse(path)
            row = conn.execute(
                "SELECT article_updated FROM chunks WHERE source_url = %s LIMIT 1",
                (art["source"],),
            ).fetchone()
            if row and row[0] == art["updated"]:
                skipped += 1
                continue
            chunks = chunk(art)
            vectors = embed(
                client,
                [
                    f"{DOC_PREFIX}{art['title']} > {h}\n{c}" if h
                    else f"{DOC_PREFIX}{art['title']}\n{c}"
                    for h, c in chunks
                ],
            )
            with conn.transaction():
                conn.execute("DELETE FROM chunks WHERE source_url = %s", (art["source"],))
                with conn.cursor() as cur:
                    cur.executemany(
                        "INSERT INTO chunks (source_url, title, heading, chunk_index,"
                        " content, article_updated, embedding)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        [
                            (art["source"], art["title"], h, i, c, art["updated"], v)
                            for i, ((h, c), v) in enumerate(zip(chunks, vectors))
                        ],
                    )
            done += 1
            total += len(chunks)
            print(f"[{n}/{len(files)}] {path.name}: {len(chunks)} chunks")
        print(f"ingested {done} articles ({total} chunks), skipped {skipped} unchanged")


if __name__ == "__main__":
    main()
