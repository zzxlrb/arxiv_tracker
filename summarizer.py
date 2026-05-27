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

PROMPT = """你是一位研究者的论文助手，研究者专注于 3D 网格生成（mesh generation）、网格编辑（mesh editing）以及使用神经网络和 AI Agent 进行自动化网格创建。

标题：{title}
作者：{authors}
摘要：{abstract}

请注意：研究关注的是计算机图形学和几何处理中的 3D 几何网格（三角网格、四面体网格、曲面网格等）。如果你的内容是关于无线 mesh 网络、data mesh、service mesh 或其他非几何领域的 "mesh"，则不应被推荐，打分应该为 1-3 分。

请用中文回答，提供以下信息：
1. 核心思想（一句话）
2. 关键技术方法
3. 对 3D 网格生成/编辑研究的意义（如果不相关请说明原因）
4. 相关性评分（1-10 分）"""


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
