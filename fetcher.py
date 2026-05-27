import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import List, Set

import arxiv

from config import ARXIV_MAX_RESULTS, ARXIV_LOOKBACK_DAYS

logger = logging.getLogger(__name__)

client = arxiv.Client(page_size=ARXIV_MAX_RESULTS)

QUERIES = [
    'abs:"mesh generation"',
    'abs:"mesh editing"',
    'abs:"3D mesh"',
    'abs:"mesh reconstruction"',
    'abs:"mesh deformation"',
    'abs:"mesh processing"',
]


def _extract_arxiv_id(entry_id: str) -> str:
    return entry_id.split("/")[-1].split("v")[0]


def _authors_string(authors) -> str:
    return ", ".join(a.name for a in authors)


def _search_query(query: str, cutoff: datetime, seen_ids: Set[str]) -> List[dict]:
    """Search arXiv for a single query. Returns matching papers."""
    papers = []
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
        logger.error("arXiv search failed for '%s': %s", query, e)

    return papers


def fetch_papers() -> List[dict]:
    """Search arXiv with all queries in parallel, deduplicate, and filter by date."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=ARXIV_LOOKBACK_DAYS)
    seen_ids: Set[str] = set()
    all_papers = []

    with ThreadPoolExecutor(max_workers=len(QUERIES)) as executor:
        futures = {
            executor.submit(_search_query, q, cutoff, seen_ids): q
            for q in QUERIES
        }
        for future in as_completed(futures):
            query = futures[future]
            try:
                papers = future.result()
                all_papers.extend(papers)
                logger.info("Query '%s': %d papers", query, len(papers))
            except Exception as e:
                logger.error("Query '%s' failed: %s", query, e)

    logger.info("Fetched %d papers (%d unique) across %d queries",
                len(all_papers), len(seen_ids), len(QUERIES))
    return all_papers
