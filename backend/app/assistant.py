import psycopg
from openai import AsyncOpenAI
from pgvector.psycopg import register_vector_async

from .config import settings

SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""

QUERY_PREFIX = "search_query: "  # pairs with DOC_PREFIX in scripts/ingest.py


async def retrieve(client: AsyncOpenAI, query: str, k: int = 5) -> list[dict]:
    resp = await client.embeddings.create(
        model=settings.embed_model, input=QUERY_PREFIX + query
    )
    async with await psycopg.AsyncConnection.connect(
        settings.neon_database_url
    ) as conn:
        await register_vector_async(conn)
        cur = await conn.execute(
            "SELECT source_url, title, heading, content FROM chunks"
            " ORDER BY embedding <=> %s::vector LIMIT %s",
            (resp.data[0].embedding, k),
        )
        rows = await cur.fetchall()
    return [
        {"url": u, "title": t, "heading": h, "content": c} for u, t, h, c in rows
    ]


def build_messages(history: list[dict], chunks: list[dict]) -> list[dict]:
    if chunks:
        docs = "\n\n".join(
            f"Article URL: {c['url']}\n"
            f"{c['title']}{' > ' + c['heading'] if c['heading'] else ''}\n"
            f"{c['content']}"
            for c in chunks
        )
    else:
        docs = "No matching docs found. Say you cannot answer from the docs."
    context = (
        f"Uploaded docs:\n\n{docs}\n\n"
        "Reply format: at most 5 bullet points, then up to 3 lines of the form "
        "'Article URL: <url>' copied from the docs above."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": context},
        *(m for m in history if m["role"] != "system"),
    ]
