import argparse
import re
from pathlib import Path

import requests
from markdownify import markdownify

URL = "https://support.optisigns.com/api/v2/help_center/en-us/articles.json"
OUT = Path(__file__).resolve().parent.parent / "data" / "articles"


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80] or "article"


def fetch(limit: int) -> list[dict]:
    articles: list[dict] = []
    url: str | None = f"{URL}?per_page={min(limit, 100)}"
    while url and len(articles) < limit:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        articles += [a for a in data["articles"] if not a["draft"]]
        url = data["next_page"]
    return articles[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull help-center articles as markdown")
    parser.add_argument("-n", "--limit", type=int, default=40, help="number of articles (default 40)")
    parser.add_argument("--all", action="store_true", help="pull every article")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    articles = fetch(10**9 if args.all else args.limit)

    # Files already on disk: article id (from the Source line) -> keep old copy.
    pulled_ids: set[str] = set()
    for f in OUT.glob("*.md"):
        m = re.search(r"^Source: .*/articles/(\d+)", f.read_text(encoding="utf-8"), re.M)
        if m:
            pulled_ids.add(m.group(1))

    skipped = 0
    for a in articles:
        if str(a["id"]) in pulled_ids:
            skipped += 1
            continue
        slug = slugify(a["title"])
        if (OUT / f"{slug}.md").exists():  # different article, same title
            slug = f"{slug}-{a['id']}"
        body = markdownify(a["body"] or "", heading_style="ATX").strip()
        text = (
            f"# {a['title']}\n\n"
            f"Source: {a['html_url']}\n"
            f"Updated: {a['updated_at']}\n\n"
            f"{body}\n"
        )
        (OUT / f"{slug}.md").write_text(text, encoding="utf-8")
    print(f"wrote {len(articles) - skipped} new files to {OUT}, skipped {skipped} already pulled")


if __name__ == "__main__":
    main()
