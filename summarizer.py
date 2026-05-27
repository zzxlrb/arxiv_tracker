import logging
import re

from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

PROMPT = """Summarize the following paper for a researcher working on neural mesh generation and automated mesh creation.

Title: {title}
Authors: {authors}
Abstract: {abstract}

Please provide:
1. Core idea (one sentence)
2. Key method / technical approach
3. Why it matters for mesh generation research
4. Relevance score (1-10)"""


def _parse_score(text: str) -> int:
    """Extract relevance score from LLM response. Defaults to 5 if parsing fails."""
    # Find the line containing "relevance score", take the last number on it.
    # e.g. "4. Relevance score (1-10): 8" -> nums are [4, 1, 10, 8], take 8.
    for line in text.split("\n"):
        if "relevance score" in line.lower():
            nums = re.findall(r"\d+", line)
            if nums:
                score = int(nums[-1])
                return min(max(score, 1), 10)
    # Fallback: scan lines from bottom for any number 1-10
    for line in reversed(text.strip().split("\n")):
        nums = re.findall(r"\b(\d+)\b", line)
        if nums:
            score = int(nums[-1])
            if 1 <= score <= 10:
                return score
    logger.warning("Could not parse relevance score, defaulting to 5")
    return 5


def summarize_paper(paper: dict) -> dict:
    """Call DeepSeek V4 to summarize a paper. Returns paper dict enriched with
    core_idea, key_method, why_matters, and relevance_score fields."""
    prompt = PROMPT.format(
        title=paper["title"],
        authors=paper["authors"],
        abstract=paper["abstract"],
    )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("DeepSeek API failed for '%s': %s", paper["title"][:60], e)
        return {
            **paper,
            "core_idea": "Summary unavailable",
            "key_method": "Summary unavailable",
            "why_matters": "Summary unavailable",
            "relevance_score": 0,
        }

    paper["relevance_score"] = _parse_score(summary)

    # Split summary into sections by numbered lines
    sections = re.split(r"\n\s*\d+\.\s*", summary)
    sections = [s.strip() for s in sections if s.strip()]

    paper["core_idea"] = sections[0] if len(sections) > 0 else summary
    paper["key_method"] = sections[1] if len(sections) > 1 else ""
    paper["why_matters"] = sections[2] if len(sections) > 2 else ""

    return paper


def summarize_papers(papers: list[dict]) -> list[dict]:
    """Summarize all papers. Failed summaries get score 0 and placeholder text."""
    results = []
    for paper in papers:
        logger.info("Summarizing: %s", paper["title"][:80])
        results.append(summarize_paper(paper))
    return results
