import re

from markdownify import markdownify


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80] or "article"


def to_markdown(article: dict) -> str:
    body = markdownify(article["body"] or "", heading_style="ATX").strip()
    return (
        f"# {article['title']}\n\n"
        f"Source: {article['html_url']}\n"
        f"Updated: {article['updated_at']}\n\n"
        f"{body}\n"
    )
