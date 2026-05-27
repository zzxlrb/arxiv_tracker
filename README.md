# arXiv Tracker — 网格生成论文速递

每日自动搜索 arXiv 上关于 3D 网格生成与编辑的最新论文，使用 DeepSeek V4 进行中文总结和相关性评分，通过邮件推送 Top N 篇精选。

## 功能

- 多关键词并行搜索 arXiv，限定摘要精确匹配
- DeepSeek V4 生成中文结构化总结（核心思想 / 关键方法 / 研究意义 / 相关性评分）
- 按相关性排序，每日推送 Top N 篇
- 去重机制，同一篇论文不会重复发送
- Brevo API 发送 HTML 邮件，穿透防火墙
- 静默模式，适合 cron 定时任务
- 并行搜索与并行总结，数秒完成

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/zzxlrb/arxiv_tracker.git
cd arxiv_tracker

# 2. 安装 uv（如果没有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. 创建环境并安装依赖
uv venv
uv pip install -r requirements.txt

# 4. 配置 .env
cp .env.example .env
# 编辑 .env，填入 API Key 和邮箱
```

## 配置 (.env)

```bash
# DeepSeek API
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# arXiv
ARXIV_MAX_RESULTS=10
ARXIV_LOOKBACK_DAYS=7
DIGEST_TOP_N=5

# Brevo 邮件 API
BREVO_API_KEY=xkeysib-xxx
SENDER_EMAIL=your-email@qq.com
RECEIVER_EMAIL=your-email@gmail.com

# 静默模式（服务器推荐）
QUIET=1
LOG_FILE=digest.log
```

## 使用

```bash
# 手动运行一次
uv run python main.py

# 定时任务（每天早上 8 点）
crontab -e
# 0 8 * * * cd /path/to/arxiv_tracker && uv run python main.py
```

## 项目结构

```
arxiv_tracker/
├── main.py          # 主流程编排
├── config.py        # 配置加载
├── fetcher.py       # arXiv 多关键词并行搜索
├── dedup.py         # 去重（seen_papers.json）
├── summarizer.py    # DeepSeek V4 并行总结
├── mailer.py        # Brevo API 邮件发送
├── .env.example     # 配置模板
└── requirements.txt
```

## 搜索关键词

所有查询限定在摘要（abs）中匹配，可在 `fetcher.py` 中修改：

- mesh generation / editing 数据集
- mesh generation / editing
- 3D mesh
- mesh reconstruction / deformation / processing

## 自定义

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DIGEST_TOP_N` | 5 | 每日推送篇数 |
| `ARXIV_LOOKBACK_DAYS` | 7 | 回溯天数 |
| `ARXIV_MAX_RESULTS` | 10 | 每关键词最多返回数 |
| `DEEPSEEK_MODEL` | deepseek-chat | LLM 模型 |
