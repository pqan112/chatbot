from dataclasses import dataclass, field

from ..storage.manifest import Entry


@dataclass
class Delta:
    added: list[dict] = field(default_factory=list)
    updated: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


def compare(scraped: list[dict], manifest: dict[str, Entry]) -> Delta:
    """Classify scraped records (with source_url, hash) against the manifest."""
    delta = Delta()
    for a in scraped:
        old = manifest.get(a["source_url"])
        if old is None:
            delta.added.append(a)
        elif old.hash != a["hash"]:
            delta.updated.append(a)
        else:
            delta.skipped.append(a)
    return delta
