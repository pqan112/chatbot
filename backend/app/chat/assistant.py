from openai import AsyncOpenAI

from ..config import settings

SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""


async def retrieve(client: AsyncOpenAI, query: str, k: int = 5) -> list[dict]:
    page = await client.vector_stores.search(
        settings.vector_store_id, query=query, max_num_results=k
    )
    return [
        {
            "url": (r.attributes or {}).get("source_url", ""),
            "title": (r.attributes or {}).get("title", r.filename),
            "content": "\n".join(p.text for p in r.content),
        }
        for r in page.data
    ]


def build_messages(history: list[dict], chunks: list[dict]) -> list[dict]:
    if chunks:
        docs = "\n\n".join(
            f"Article URL: {c['url']}\n{c['title']}\n{c['content']}" for c in chunks
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
