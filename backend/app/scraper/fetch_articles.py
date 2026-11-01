import requests

URL = "https://support.optisigns.com/api/v2/help_center/en-us/articles.json"


def fetch_articles(limit: int | None = None) -> list[dict]:
    """Published articles from the Zendesk API, all of them when limit is None."""
    articles: list[dict] = []
    url: str | None = f"{URL}?per_page={min(limit or 100, 100)}"
    while url and (limit is None or len(articles) < limit):
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        articles += [a for a in data["articles"] if not a["draft"]]
        url = data["next_page"]
    return articles[:limit]
