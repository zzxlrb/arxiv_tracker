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

PROMPT = """你是一位计算机图形学与几何处理领域的资深研究者，你的任务是评估一篇论文对于 3D 网格生成、网格编辑以及基于神经网络和 AI Agent 的自动化网格创建研究的参考价值。

研究范围界定：关注的是计算机图形学和几何处理中的 3D 几何网格。包括三角网格、四面体网格、曲面网格、体积网格及其相关的生成、编辑、变形、简化、重建、参数化等任务。无线 mesh 网络、data mesh、service mesh 等非几何领域的论文与本研究无关，应给予 1 到 3 分的低相关性评分。

标题：{title}
作者：{authors}
摘要：{abstract}

请用中文撰写如下四个部分的专业评述。每部分使用一段连续的自然语句表述，禁止使用 Markdown 格式、加粗、斜体、破折号、箭头、星号、圆点符号、项目符号以及任何非文本装饰符号。禁止使用括号补充说明。禁止使用分号分隔多个要点。禁止以首先其次然后此外另外等逻辑连接词组织内容。

1. 核心思想
用一句话准确概括该论文的核心研究问题与主要贡献。

2. 关键技术方法
阐述论文提出的主要技术路线与核心算法设计。

3. 研究意义
说明该工作对 3D 网格生成与编辑领域的启发价值或潜在影响。若论文与 3D 网格无关则直接指出其不属于本研究范畴。

4. 相关性评分
给出 1 到 10 的整数评分。1 到 3 分表示与 3D 网格无关，4 到 6 分表示存在一定关联，7 到 10 分表示该论文直接围绕 3D 网格生成或编辑展开。"""


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
