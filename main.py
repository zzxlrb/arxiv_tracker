import logging
import sys

from fetcher import fetch_papers
from dedup import filter_new_papers, mark_sent
from summarizer import summarize_papers
from mailer import send_digest, send_empty_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("arxiv_digest")


def main() -> None:
    logger.info("=== Research Digest Pipeline Start ===")

    # 1. Fetch papers from arXiv
    papers = fetch_papers()
    logger.info("Fetched %d papers from arXiv", len(papers))

    if not papers:
        logger.info("No papers found in lookback window")
        send_empty_digest()
        logger.info("=== Pipeline Complete (no papers) ===")
        return

    # 2. Filter out previously sent papers
    papers = filter_new_papers(papers)
    logger.info("After dedup: %d new papers", len(papers))

    if not papers:
        logger.info("All papers already sent")
        send_empty_digest()
        logger.info("=== Pipeline Complete (all seen) ===")
        return

    # 3. Summarize with DeepSeek V4
    papers = summarize_papers(papers)

    # 4. Sort by relevance, take top 5
    papers.sort(key=lambda p: p["relevance_score"], reverse=True)
    top5 = papers[:5]
    logger.info("Top 5 papers selected (scores: %s)", [p["relevance_score"] for p in top5])

    # 5. Mark top 5 as sent before sending (if send fails, they're still recorded)
    mark_sent(top5)

    # 6. Send email
    try:
        send_digest(top5)
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        sys.exit(1)

    logger.info("=== Pipeline Complete ===")


if __name__ == "__main__":
    main()
