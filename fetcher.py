import logging
from datetime import datetime, timedelta, timezone
from typing import List

import arxiv

from config import ARXIV_MAX_RESULTS, ARXIV_LOOKBACK_DAYS

logger = logging.getLogger(__name__)

client = arxiv.Client(page_size=ARXIV_MAX_RESULTS)

QUERIES = [
    "neural mesh generation",
    "AI mesh generation",
    "mesh generation with large language model",
    "code generation for 3D mesh",
    "automated mesh generation agent",
]


def _extract_arxiv_id(entry_id: str) -> str:
    """Extract arxiv ID from entry_id URL.

    e.g. 'http://arxiv.org/abs/2101.12345v2' -> '2101.12345'
    """
    return entry_id.split("/")[-1].split("v")[0]


def _authors_string(authors) -> str:
    """Convert arxiv author list to comma-separated string."""
    return ", ".join(a.name for a in authors)


def fetch_papers() -> List[dict]:
    """Search arXiv with all queries, deduplicate, and filter to lookback window.

    Returns list of paper dicts with keys: arxiv_id, title, authors,
    abstract, published, url.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=ARXIV_LOOKBACK_DAYS)
    seen_ids = set()
    papers = []

    for query in QUERIES:
        logger.info("Searching arXiv: %s", query)
        search = arxiv.Search(
            query=query,
            max_results=ARXIV_MAX_RESULTS,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

        try:
            for result in client.results(search):
                arxiv_id = _extract_arxiv_id(result.entry_id)
                if arxiv_id in seen_ids:
                    continue
                pub = result.published
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if pub < cutoff:
                    continue
                seen_ids.add(arxiv_id)
                papers.append({
                    "arxiv_id": arxiv_id,
                    "title": result.title.strip(),
                    "authors": _authors_string(result.authors),
                    "abstract": result.summary.strip(),
                    "published": result.published,
                    "url": result.entry_id,
                })
        except Exception as e:
            logger.error("arXiv search failed for query '%s': %s", query, e)
            continue

    logger.info("Fetched %d papers across %d queries", len(papers), len(QUERIES))
    return papers
