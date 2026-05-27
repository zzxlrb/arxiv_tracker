import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

PROMPT = """You are evaluating a paper's relevance to a researcher working on 3D mesh generation, mesh editing, and automated mesh creation using neural methods and AI agents.

Title: {title}
Authors: {authors}
Abstract: {abstract}

IMPORTANT: This research is about 3D geometry meshes (triangle meshes, tetrahedral meshes, surface meshes, volumetric meshes used in computer graphics, geometry processing, and finite element analysis). Papers about mesh networks, wireless mesh, data mesh, service mesh, or any non-geometry "mesh" are NOT relevant and should receive a score of 1-3.

Please provide:
1. Core idea (one sentence)
2. Key method / technical approach
3. Why it matters for 3D mesh generation/editing research (if not relevant, briefly explain why)
4. Relevance score (1-10, where 1-3 = not relevant to 3D meshes, 4-6 = tangentially related, 7-10 = directly about 3D mesh generation/editing)"""


def _parse_score(text: str) -> int:
    for line in text.split("\n"):
        if "relevance score" in line.lower():
            nums = re.findall(r"\d+", line)
            if nums:
                score = int(nums[-1])
                return min(max(score, 1), 10)
    for line in reversed(text.strip().split("\n")):
        nums = re.findall(r"\b(\d+)\b", line)
        if nums:
            score = int(nums[-1])
            if 1 <= score <= 10:
                return score
    logger.warning("Could not parse relevance score, defaulting to 5")
    return 5


def _strip_header(text: str) -> str:
    lines = text.strip().split("\n", 1)
    if len(lines) > 1:
        return lines[1].strip()
    return text.strip()


def summarize_paper(paper: dict) -> dict:
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

    first_num = re.search(r"\n\s*\*{0,2}1\.\s", summary)
    if first_num:
        summary = summary[first_num.start():].strip()

    sections = re.split(r"\n\s*\*{0,2}\d+\.\s*", summary)
    sections = [s.strip() for s in sections if s.strip()]

    paper["core_idea"] = _strip_header(sections[0]) if len(sections) > 0 else summary
    paper["key_method"] = _strip_header(sections[1]) if len(sections) > 1 else ""
    paper["why_matters"] = _strip_header(sections[2]) if len(sections) > 2 else ""

    return paper


def summarize_papers(papers: list[dict]) -> list[dict]:
    logger.info("Summarizing %d papers in parallel", len(papers))
    index = {p["arxiv_id"]: i for i, p in enumerate(papers)}
    results = [None] * len(papers)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(summarize_paper, p): i for i, p in enumerate(papers)}
        for future in as_completed(futures):
            i = futures[future]
            results[i] = future.result()

    return [r for r in results if r is not None]
