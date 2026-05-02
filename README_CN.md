# paper_router

[English](./README.md) | 中文

[![Tests](https://img.shields.io/badge/tests-80%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)]()

学术论文搜索聚合层。跨多个数据源异步检索论文，统一格式输出，支持去重、过滤和限流。

专为 **Agent 调用** 设计 — CLI 输出换行分隔的 JSON 流（NDJSON），错误可解析，单个数据源故障不阻塞整体查询。

## 特性

- **4 个数据源**：OpenAlex、Semantic Scholar、CrossRef、arXiv
- **数据源级容错**：单个数据源失败不影响其他结果
- **去重**：优先按 DOI 去重，其次按标题+日期
- **过滤**：日期范围、期刊分区（Q1–Q4）
- **限流**：每个数据源独立的异步速率限制
- **两种接口**：CLI（脚本/Agent）和 MCP（AI 主机）

## 快速开始

```bash
# 安装
poetry install

# 搜索（默认使用全部 4 个数据源）
paper-router search --queries "silicon anode" --limit 10

# 带日期过滤
paper-router search --queries "battery cathode" --start_date 2024-01-01 --end_date 2024-12-31

# 指定数据源
paper-router search --queries "perovskite solar" --providers openalex crossref
```

## CLI 参数

```
paper-router search --queries QUERIES [--providers PROVIDERS ...]
                   [--start_date YYYY-MM-DD] [--end_date YYYY-MM-DD]
                   [--limit N] [--quartiles Q1 Q2 ...]
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `--queries` | 是 | 搜索关键词（支持多个） |
| `--providers` | 否 | 数据源（默认全部）。可选：`openalex`、`semantic_scholar`、`crossref`、`arxiv` |
| `--start_date` | 否 | 最早发表日期 |
| `--end_date` | 否 | 最晚发表日期 |
| `--limit` | 否 | 每个查询最大返回数 |
| `--quartiles` | 否 | 按 JCR 分区过滤（如 `Q1 Q2`） |

### 输出格式（NDJSON 流）

stdout 输出换行分隔的 JSON 流。每行是一个独立事件，逐行读取即可增量处理。

**进度事件** — 每个数据源调用前发出：
```json
{"finish":false,"type":"progress","current":1,"total":4,"message":"searching openalex for 'silicon anode'..."}
```

**论文事件** — 数据源返回结果时立即发出：
```json
{"finish":false,"type":"papers","provider":"openalex","query":"silicon anode","count":50,"papers":[
  {"source":"openalex","external_id":"W123","title":"...","authors":["..."],"publication_date":"2024-06-01","doi":"10.xxx","venue":"Nature","abstract":"...","url":"https://...","quartile":"Q1"}
]}
```

**错误事件** — 单个数据源失败时发出（继续其他查询）：
```json
{"finish":false,"type":"error","provider":"arxiv","query":"silicon anode","message":"Connection timeout"}
```

**结果事件** — 始终在最后一行。去重排序后的最终结果：
```json
{"finish":true,"type":"result","success":true,"queries":["silicon anode"],"providers":["openalex","arxiv"],"count":27,"results":[...],"warnings":["JCR quartile data is outdated..."]}
```

**致命错误**：
```json
{"finish":true,"type":"result","success":false,"error":"Unknown provider(s): fake_provider","available_providers":["arxiv","crossref","openalex","semantic_scholar"]}
```

> **消费方式**：每行是一个独立 JSON，`finish` 字段标记是否结束。`papers` 事件包含每个数据源的原始结果（未去重），`result` 事件包含最终去重集。

### 部分失败

当某些数据源失败时，仍返回其他数据源的结果。`result` 事件的 `warnings` 字段列出所有异常。

## Python API

```python
import asyncio
from datetime import date

from paper_router import PaperRouter, SearchRequest
from paper_router.providers import OpenAlexProvider, SemanticScholarProvider


async def main():
    router = PaperRouter([OpenAlexProvider(), SemanticScholarProvider()])
    papers = await router.search(SearchRequest(
        query="silicon anode",
        start_date=date(2024, 1, 1),
        limit=20,
    ))
    for paper in papers:
        print(f"{paper.publication_date} | {paper.title} ({paper.source})")
    await router.aclose()


asyncio.run(main())
```

## 数据源

| 数据源 | CLI 名称 | 限流 | API Key | 说明 |
|---|---|---|---|---|
| OpenAlex | `openalex` | 10 req/s | 可选 | 免费，全学科 |
| Semantic Scholar | `semantic_scholar` | 1 req/s | 可选 | AI/CS 方向 |
| CrossRef | `crossref` | 50 req/s | 可选 | DOI 注册库，全学科 |
| arXiv | `arxiv` | 3 req/s | 无需 | 预印本（物理、数学、CS） |

大部分数据源无需 API Key 即可使用。在 `.env` 文件中设置（参见 `.env.example`）可获得更高限额。

## MCP 服务器

支持 Model Context Protocol 的 AI 主机可使用：

```bash
# 启动 MCP 服务器（stdio 传输）
paper-router-mcp
```

可用工具：
- `search_papers(query, providers?, start_date?, end_date?, limit?)` — 搜索论文
- `list_providers()` — 列出可用数据源

## 测试

```bash
poetry install
.venv/Scripts/pytest -q
# 80 passed
```

## 项目结构

```
src/paper_router/
├── cli.py              # CLI 入口（面向 Agent）
├── mcp_server.py       # MCP 服务器入口
├── registry.py         # 共享数据源注册表
├── router.py           # PaperRouter：搜索、去重、过滤
├── models.py           # SearchRequest、Paper、Quartile
├── config.py           # .env / 环境变量配置加载
├── filters.py          # 日期范围和分区过滤
├── rate_limit.py       # 异步限流器
└── providers/
    ├── base.py         # PaperProvider 抽象基类
    ├── openalex.py     # OpenAlex 实现
    ├── semantic_scholar.py
    ├── crossref.py     # CrossRef 实现
    └── arxiv.py        # arXiv 实现（XML）
```

## 添加新数据源

1. 创建 `src/paper_router/providers/your_provider.py`
2. 继承 `PaperProvider`，实现 `default_rate_limit()`、`build_params()`、`parse_response()`
3. 非 JSON API 则重写 `_parse_response_text()`
4. 在 `providers/__init__.py` 和 `registry.py` 中注册

## 许可证

MIT
