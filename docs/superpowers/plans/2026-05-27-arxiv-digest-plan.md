# Research Digest Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily arXiv digest that searches for neural/agent mesh generation papers, summarizes them with DeepSeek V4, and emails the top 5 to the researcher.

**Architecture:** Five focused modules (config, fetcher, dedup, summarizer, mailer) orchestrated by main.py. Each module has one responsibility and a well-defined interface. Data flows as plain dicts through the pipeline.

**Tech Stack:** Python 3.13, `arxiv`, `openai` (DeepSeek-compatible), `python-dotenv`, `smtplib`

**Spec:** `docs/superpowers/specs/2026-05-27-arxiv-digest-design.md`

---

### Task 1: Project Scaffold

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `requirements.txt`

- [ ] **Step 1: Create .gitignore**

```python
# .gitignore
.env
seen_papers.json
__pycache__/
*.pyc
.DS_Store
```

Write to `.gitignore`.

- [ ] **Step 2: Create .env.example**

```
# DeepSeek API
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# arXiv
ARXIV_MAX_RESULTS=10
ARXIV_LOOKBACK_DAYS=7

# Email (QQ SMTP)
SMTP_SERVER=smtp.qq.com
SMTP_PORT=465
SENDER_EMAIL=your-email@qq.com
SENDER_AUTH_CODE=your-auth-code
RECEIVER_EMAIL=your-email@gmail.com
```

Write to `.env.example`.

- [ ] **Step 3: Create requirements.txt**

```
arxiv>=2.1.0
openai>=1.0.0
python-dotenv>=1.0.0
```

Write to `requirements.txt`.

- [ ] **Step 4: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: all three packages install successfully.

- [ ] **Step 5: Commit**

```bash
git add .gitignore .env.example requirements.txt
git commit -m "chore: add project scaffold"
```

---

### Task 2: Config Module

**Files:**
- Create: `config.py`

- [ ] **Step 1: Write config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()


def get_env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def get_int(key: str, default: int) -> int:
    val = os.getenv(key, "")
    if val == "":
        return default
    return int(val)


DEEPSEEK_API_KEY = get_env("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = get_env("DEEPSEEK_MODEL", "deepseek-chat")

ARXIV_MAX_RESULTS = get_int("ARXIV_MAX_RESULTS", 10)
ARXIV_LOOKBACK_DAYS = get_int("ARXIV_LOOKBACK_DAYS", 7)

SMTP_SERVER = get_env("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = get_int("SMTP_PORT", 465)
SENDER_EMAIL = get_env("SENDER_EMAIL")
SENDER_AUTH_CODE = get_env("SENDER_AUTH_CODE")
RECEIVER_EMAIL = get_env("RECEIVER_EMAIL")
```

Write to `config.py`.

- [ ] **Step 2: Create .env for local dev**

Copy `.env.example` to `.env` and fill in real values. (Do this manually — not committed.)

- [ ] **Step 3: Verify config loads**

Run: `python -c "import config; print(config.DEEPSEEK_BASE_URL)"`
Expected: prints `https://api.deepseek.com` (or the value from your `.env`).

- [ ] **Step 4: Commit**

```bash
git add config.py
git commit -m "feat: add config module"
```

---

### Task 3: Dedup Module

**Files:**
- Create: `dedup.py`

- [ ] **Step 1: Write dedup.py**

```python
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
```

Write to `dedup.py`.

- [ ] **Step 2: Verify dedup logic manually**

Run:
```python
python -c "
import dedup, json, os
# cleanup any existing file
if os.path.exists('seen_papers.json'):
    os.remove('seen_papers.json')

papers = [
    {'arxiv_id': '2101.001', 'title': 'A'},
    {'arxiv_id': '2101.002', 'title': 'B'},
    {'arxiv_id': '2101.001', 'title': 'A duplicate'},
]
new_papers = dedup.filter_new_papers(papers)
assert len(new_papers) == 3, f'Expected 3, got {len(new_papers)}'

dedup.mark_sent(new_papers[:2])

remaining = dedup.filter_new_papers(papers)
assert len(remaining) == 1
assert remaining[0]['arxiv_id'] == '2101.002'
print('All assertions passed')
"
```
Expected: prints "All assertions passed".

- [ ] **Step 3: Commit**

```bash
git add dedup.py
git commit -m "feat: add dedup module with seen_papers.json persistence"
```

---

### Task 4: Fetcher Module

**Files:**
- Create: `fetcher.py`

- [ ] **Step 1: Write fetcher.py**

```python
import logging
from datetime import datetime, timedelta, timezone
from typing import List

import arxiv

from config import ARXIV_MAX_RESULTS, ARXIV_LOOKBACK_DAYS

logger = logging.getLogger(__name__)

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
            for result in search.results():
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
```

Write to `fetcher.py`.

- [ ] **Step 2: Verify fetcher runs**

Run: `python -c "import logging; logging.basicConfig(level=logging.INFO); from fetcher import fetch_papers; papers = fetch_papers(); print(f'Found {len(papers)} papers')"`
Expected: logs search activity, prints paper count (likely 0 in an empty test, or some number).

- [ ] **Step 3: Commit**

```bash
git add fetcher.py
git commit -m "feat: add arXiv fetcher with multi-query search and date filter"
```

---

### Task 5: Summarizer Module

**Files:**
- Create: `summarizer.py`

- [ ] **Step 1: Write summarizer.py**

```python
import json
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
```

Write to `summarizer.py`.

- [ ] **Step 2: Test score parsing**

Run:
```python
python -c "
from summarizer import _parse_score
assert _parse_score('...\n4. Relevance score (1-10): 8') == 8
assert _parse_score('relevance score: 3') == 3
assert _parse_score('no score here') == 5
assert _parse_score('blah 7 blah') == 7
print('All assertions passed')
"
```
Expected: prints "All assertions passed".

- [ ] **Step 3: Commit**

```bash
git add summarizer.py
git commit -m "feat: add DeepSeek V4 summarizer with relevance scoring"
```

---

### Task 6: Mailer Module

**Files:**
- Create: `mailer.py`

- [ ] **Step 1: Write mailer.py**

```python
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from typing import List

from config import (
    SMTP_SERVER,
    SMTP_PORT,
    SENDER_EMAIL,
    SENDER_AUTH_CODE,
    RECEIVER_EMAIL,
)

logger = logging.getLogger(__name__)


def _render_html(papers: List[dict]) -> str:
    """Render the HTML email body for a list of summarized papers."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    rows = []

    for i, p in enumerate(papers, 1):
        rows.append(f"""
        <div style="margin-bottom:30px; padding-bottom:20px; border-bottom:1px solid #eee;">
            <h2 style="color:#1a1a2e; margin-bottom:8px;">{i}. {p['title']}</h2>
            <p style="color:#555; margin:4px 0;"><b>Authors:</b> {p['authors']}</p>
            <p style="margin:4px 0;"><a href="{p['url']}" style="color:#2563eb;">Paper Link</a></p>
            <p style="margin:4px 0;"><b>Relevance:</b> {p['relevance_score']}/10</p>
            <div style="margin-top:12px; padding:12px; background:#f8f9fa; border-radius:6px;">
                <p style="margin:4px 0;"><b>Core Idea:</b> {p['core_idea']}</p>
                <p style="margin:4px 0;"><b>Key Method:</b> {p['key_method']}</p>
                <p style="margin:4px 0;"><b>Why It Matters:</b> {p['why_matters']}</p>
            </div>
        </div>
        """)

    return f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif; max-width:700px; margin:0 auto; padding:20px; background:#fff;">
        <div style="background:#1a1a2e; color:#fff; padding:20px; border-radius:8px; margin-bottom:24px;">
            <h1 style="margin:0; font-size:22px;">Daily arXiv Digest — Mesh Generation</h1>
            <p style="margin:8px 0 0; opacity:0.8; font-size:14px;">{date_str} — Top {len(papers)} Papers</p>
        </div>
        {"".join(rows)}
        <p style="color:#999; font-size:12px; margin-top:30px; text-align:center;">
            Generated by Research Digest Pipeline
        </p>
    </body>
    </html>
    """


def send_digest(papers: List[dict]) -> None:
    """Render and send the HTML email digest."""
    html = _render_html(papers)
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = f"[arXiv Digest] Neural Mesh Generation — {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    logger.info("Sending digest to %s with %d papers", RECEIVER_EMAIL, len(papers))
    server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
    server.login(SENDER_EMAIL, SENDER_AUTH_CODE)
    server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    server.quit()
    logger.info("Digest sent successfully")


def send_empty_digest() -> None:
    """Send a 'no new papers' notification."""
    html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif; max-width:500px; margin:0 auto; padding:20px;">
        <h2>No new papers today</h2>
        <p>arXiv had no new mesh generation papers matching your queries in the past 7 days.</p>
        <p style="color:#999;">— Research Digest Pipeline, {datetime.now().strftime('%Y-%m-%d')}</p>
    </body>
    </html>
    """
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = f"[arXiv Digest] No New Papers — {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
    server.login(SENDER_EMAIL, SENDER_AUTH_CODE)
    server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    server.quit()
    logger.info("Empty digest sent")
```

Write to `mailer.py`.

- [ ] **Step 2: Verify HTML renders without errors**

Run:
```python
python -c "
from mailer import _render_html
papers = [{
    'arxiv_id': '2101.001',
    'title': 'Test Paper',
    'authors': 'Author One, Author Two',
    'url': 'https://arxiv.org/abs/2101.001',
    'relevance_score': 8,
    'core_idea': 'A novel approach.',
    'key_method': 'Deep learning.',
    'why_matters': 'Advances the field.',
}]
html = _render_html(papers)
assert '<h1>' in html
assert 'Test Paper' in html
assert '8/10' in html
print('HTML renders correctly')
"
```
Expected: prints "HTML renders correctly".

- [ ] **Step 3: Commit**

```bash
git add mailer.py
git commit -m "feat: add HTML mailer with QQ SMTP support"
```

---

### Task 7: Main Orchestration

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write main.py**

```python
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
```

Write to `main.py`.

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: add main orchestration pipeline"
```

---

### Task 8: End-to-End Test

- [ ] **Step 1: Dry run without email**

First, verify the pipeline runs end-to-end by temporarily commenting out `send_digest(top5)` in `main.py` and adding `print(f"Would send: {len(top5)} papers")` instead.

Run: `python main.py`
Expected: logs through the full pipeline, shows paper titles, relevance scores, and "Would send: N papers".

- [ ] **Step 2: Restore email and do full test**

Undo the edit from Step 1. Ensure `.env` has real credentials.

Run: `python main.py`
Expected: email arrives in Gmail inbox with HTML formatting.

- [ ] **Step 3: Verify dedup on second run**

Run: `python main.py` again.
Expected: "All papers already sent" or new papers only (not the same 5 from before).

- [ ] **Step 4: Commit final**

```bash
git add main.py
git commit -m "chore: finalize pipeline after e2e test"
```

---

### Post-Implementation: Server Deployment

After local testing is stable:

1. Copy project to server: `scp -r arxiv_digest/ user@server:/home/user/`
2. On server: `pip install -r requirements.txt`
3. Set environment variables in `~/.bashrc` or `/etc/environment`
4. Add cron job: `crontab -e` → `0 8 * * * /usr/bin/python3 /home/user/arxiv_digest/main.py`
5. Monitor: check email daily for first week
