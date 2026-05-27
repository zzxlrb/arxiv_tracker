# Research Digest Pipeline — Design Spec

**Date:** 2026-05-27
**Status:** approved

## Overview

Daily automated research paper digest. Searches arXiv for neural/agent-driven mesh generation papers published in the past 7 days, filters out previously sent papers, summarizes the top 5 most relevant with DeepSeek V4, and sends an HTML email to the researcher.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Search | `arxiv` Python library |
| LLM | DeepSeek V4 (OpenAI-compatible API) |
| Email | `smtplib` + QQ SMTP |
| Config | `.env` file + environment variables |
| Deployment | cron on Linux server |
| Runtime | Python 3.13+ |

## Project Structure

```
arxiv_digest/
├── main.py              # Entry point, orchestrates the pipeline
├── config.py            # Loads config from .env / env vars
├── fetcher.py           # arXiv multi-query search + date filter
├── dedup.py             # Track sent papers in seen_papers.json
├── summarizer.py        # DeepSeek V4 structured paper summary
├── mailer.py            # HTML rendering + SMTP send
├── seen_papers.json     # Record of sent arxiv IDs (auto-generated)
├── .env                 # Local credentials (not committed)
├── .env.example         # Config template
├── .gitignore
├── requirements.txt     # arxiv, openai, python-dotenv
```

## Data Flow

```
.env / env vars
    ↓
main.py
    ↓ (1) fetcher: search arXiv with 5 queries → dedup across queries → filter to past 7 days
    ↓ (2) dedup: remove previously sent papers (seen_papers.json) → return new papers
    ↓ (3) summarizer: for each paper → DeepSeek V4 structured summary + relevance score (1–10)
    ↓ (4) sort by relevance → top 5
    ↓ (5) dedup: record sent arxiv IDs to seen_papers.json
    ↓ (6) mailer: render HTML email → QQ SMTP → Gmail inbox
```

## Configuration (.env)

```
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

ARXIV_MAX_RESULTS=10
ARXIV_LOOKBACK_DAYS=7

SMTP_SERVER=smtp.qq.com
SMTP_PORT=465
SENDER_EMAIL=xxx@qq.com
SENDER_AUTH_CODE=xxx
RECEIVER_EMAIL=xxx@gmail.com
```

## Search Queries

```python
QUERIES = [
    "neural mesh generation",
    "AI mesh generation",
    "mesh generation with large language model",
    "code generation for 3D mesh",
    "automated mesh generation agent",
]
```

## LLM Prompt

```python
PROMPT = """Summarize the following paper for a researcher working on neural mesh generation and automated mesh creation.

Title: {title}
Authors: {authors}
Abstract: {abstract}

Please provide:
1. Core idea (one sentence)
2. Key method / technical approach
3. Why it matters for mesh generation research
4. Relevance score (1-10)"""
```

## V1 Feature Set

- Multi-query arXiv search with cross-query deduplication
- Date filter (past 7 days)
- Deduplication persistence (`seen_papers.json`) — never send the same paper twice
- DeepSeek V4 structured summary with relevance scoring (1–10)
- **No relevance threshold** — all papers receive scores, researcher evaluates during trial
- Top 5 papers by relevance score
- HTML email via QQ SMTP to Gmail

## V2 (Future)

- Relevance threshold after calibration period
- Paper categorization (e.g., neural generation, agent-based, LLM code-gen)
- Top Picks highlight

## V1 → V2 Iteration

Each module (`fetcher`, `dedup`, `summarizer`, `mailer`) has a single responsibility and well-defined interface. V2 additions are localized:

- **Relevance threshold**: one line change in `main.py` after scoring, no module changes
- **Categorization**: add tags field to summarizer prompt output, update HTML template
- **Top Picks**: add a highlight section at the top of the HTML email

No rewrites needed. The data flow (fetch → dedup → summarize → sort → record → mail) stays the same.

## Security

- Local: `.env` with `chmod 600`, excluded from git via `.gitignore`
- Server: credentials set as system environment variables; `config.py` reads env vars first, falls back to `.env`

## Error Handling

- arXiv API failure → log error, skip send (don't send empty/spam email)
- DeepSeek API failure for individual paper → skip paper, continue with others
- SMTP failure → log error, exit non-zero (so cron can report)
- Zero papers found → send a brief "no new papers today" email

## Testing Strategy

- Manual V1 run: `python main.py` and verify email received
- Check DeepSeek summary quality by reviewing first few emails
- Calibrate search queries based on relevance scores over 1–2 weeks
