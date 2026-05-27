import json
import os
from typing import List, Set

SEEN_FILE = "seen_papers.json"


def _load_seen() -> Set[str]:
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r") as f:
        data = json.load(f)
    return set(data.get("ids", []))


def _save_seen(ids: Set[str]) -> None:
    with open(SEEN_FILE, "w") as f:
        json.dump({"ids": sorted(ids)}, f, indent=2)


def filter_new_papers(papers: List[dict]) -> List[dict]:
    """Return papers whose arxiv_id is not in seen_papers.json."""
    seen = _load_seen()
    return [p for p in papers if p["arxiv_id"] not in seen]


def mark_sent(papers: List[dict]) -> None:
    """Add paper arxiv_ids to seen_papers.json."""
    seen = _load_seen()
    for p in papers:
        seen.add(p["arxiv_id"])
    _save_seen(seen)
