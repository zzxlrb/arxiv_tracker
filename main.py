import logging
import os
import sys

from fetcher import fetch_papers
from dedup import filter_new_papers, mark_sent
from summarizer import summarize_papers
from mailer import send_digest, send_empty_digest

LOG_FILE = os.getenv("LOG_FILE", "")
QUIET = os.getenv("QUIET", "").lower() in ("1", "true", "yes")

# Suppress noisy library logs
for lib in ("arxiv", "httpx", "httpcore", "openai"):
    logging.getLogger(lib).setLevel(logging.WARNING)

if QUIET and LOG_FILE:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        filename=LOG_FILE,
    )
elif QUIET:
    logging.basicConfig(level=logging.WARNING)
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

logger = logging.getLogger("arxiv_digest")


def main() -> None:
    logger.info("=== Research Digest Pipeline Start ===")

    papers = fetch_papers()
    logger.info("Fetched %d papers from arXiv", len(papers))

    if not papers:
        logger.info("No papers found in lookback window")
        send_empty_digest()
        logger.info("=== Pipeline Complete (no papers) ===")
        return

    papers = filter_new_papers(papers)
    logger.info("After dedup: %d new papers", len(papers))

    if not papers:
        logger.info("All papers already sent")
        send_empty_digest()
        logger.info("=== Pipeline Complete (all seen) ===")
        return

    papers = summarize_papers(papers)

    papers.sort(key=lambda p: p["relevance_score"], reverse=True)
    top5 = papers[:5]
    scores = [p["relevance_score"] for p in top5]
    titles = [p["title"][:80] for p in top5]
    logger.info("Top 5 papers: %s", list(zip(titles, scores)))

    mark_sent(top5)

    try:
        send_digest(top5)
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        sys.exit(1)

    logger.info("=== Pipeline Complete ===")


if __name__ == "__main__":
    main()
