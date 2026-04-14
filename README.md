# Smart Weekly Report Agent

AI-powered agent system for automated weekly project report generation, progress tracking, and natural language querying over project data.

## Features

- **Automated report generation** — Upload site photos, PDFs, text data; the agent synthesizes a structured weekly report
- **Natural language progress queries** — Ask "XX项目进度如何？" and get answers backed by real project data
- **Multi-modal data processing** — Image OCR/VLM, PDF parsing, text chunking, vector embedding
- **RAG + SQL hybrid retrieval** — Combines structured database queries with semantic vector search
- **Streaming output** — Real-time report generation via WebSocket
- **High concurrency** — Redis caching, distributed locks, Celery async task queue

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Web Framework | FastAPI (async) |
| Agent Framework | LangChain + LangGraph |
| Database | MySQL 8.0 |
| Vector Store | Milvus 2.4 |
| Cache / Queue | Redis 7 + Celery |
| LLM | Ollama (Qwen2.5 / Llama3) |
| Embedding | BGE-large-zh-v1.5 |
| Object Storage | MinIO |

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your settings

# 2. Start infrastructure
make up

# 3. Pull LLM models
make pull-models

# 4. Initialize databases
make db-init
make milvus-init

# 5. Run the application
make dev

# 6. Open Swagger docs
open http://localhost:8000/docs
```

## Architecture

本项目采用 **九层 Agent 架构**，核心思想是 **关注点分离** —— 每层只做一件事，层与层之间通过明确接口（Protocol / ABC）通信，任意一层可独立替换而不影响其他部分。

### 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                  Layer 1 · 接口层 Interface                  │
│               app/api/    HTTP / WebSocket 端点               │
├─────────────────────────────────────────────────────────────┤
│                  Layer 2 · 感知层 Perception                 │
│           app/perception/    文档解析 / OCR / 分块             │
├─────────────────────────────────────────────────────────────┤
│                  Layer 3 · 规划层 Planning                   │
│          app/agents/planner/    任务分解与路由                  │
├─────────────────────────────────────────────────────────────┤
│                  Layer 4 · 推理层 Reasoning                  │
│           app/agents/nodes/    LLM 推理节点                   │
├─────────────────────────────────────────────────────────────┤
│                  Layer 5 · 编排层 Orchestration               │
│          app/orchestration/    LangGraph 状态机与工作流         │
├─────────────────────────────────────────────────────────────┤
│                  Layer 6 · 执行层 Action                     │
│              app/tools/    工具注册表与工具实现                  │
├─────────────────────────────────────────────────────────────┤
│                  Layer 7 · 记忆层 Memory                     │
│             app/memory/    MySQL + Milvus + Redis 统一抽象     │
├─────────────────────────────────────────────────────────────┤
│                  Layer 8 · 模型服务层 Model Service            │
│          app/model_service/    LLM / Embedding / VLM 抽象     │
├─────────────────────────────────────────────────────────────┤
│                  Layer 9 · 保障层 Infrastructure              │
│              app/core/    认证 / 限流 / 异常 / 中间件           │
└─────────────────────────────────────────────────────────────┘
```

### 各层职责

| 层 | 目录 | 职责 | 接口定义 |
|---|---|---|---|
| **接口层** | `app/api/` | HTTP/WebSocket 端点，请求校验，认证分发 | FastAPI Router |
| **感知层** | `app/perception/` | PDF/图片/文本解析，OCR，文本分块，向量化 | `DocumentProcessor` Protocol |
| **规划层** | `app/agents/planner/` | 任务类型检测，输入校验，工作流路由 | `Planner` Protocol |
| **推理层** | `app/agents/nodes/` | LLM 驱动的推理节点（写报告、审核、问答） | `ReasoningNode` Protocol |
| **编排层** | `app/orchestration/` | LangGraph 状态机定义，节点编排，条件路由 | `Workflow` Protocol |
| **执行层** | `app/tools/` | 工具注册表 + 具体工具（DB查询、向量搜索、导出） | `BaseTool` ABC |
| **记忆层** | `app/memory/` | MySQL / Milvus / Redis 统一门面 | `StructuredStore` / `VectorStore` / `CacheStore` Protocol |
| **模型服务层** | `app/model_service/` | LLM / Embedding / VLM 多后端调度（local/api/ollama） | `ModelRegistry` |
| **保障层** | `app/core/` | JWT 认证、限流、CORS、异常处理、日志 | Middleware / Exception Handlers |

### 工具注册制

执行层采用 **注册制** 设计，所有工具继承 `BaseTool` 并通过 `ToolRegistry` 注册，支持运行时扩展：

```python
# 1. 定义工具
from app.tools.base import BaseTool, ToolResult

class MyCustomTool(BaseTool):
    @property
    def name(self) -> str:
        return "custom.my_tool"

    @property
    def description(self) -> str:
        return "My custom tool description"

    def execute(self, **kwargs) -> ToolResult:
        # ... 工具逻辑
        return ToolResult(success=True, data=result)

# 2. 注册到全局注册表
from app.tools.registry import tool_registry
tool_registry.register(MyCustomTool())

# 3. 任意节点通过名称调用
result = tool_registry.execute("custom.my_tool", param1="value")
```

内置 8 个工具在应用启动时自动注册：

| 工具名 | 类 | 说明 |
|--------|-----|------|
| `db.get_project_info` | `GetProjectInfoTool` | 查询项目元数据 |
| `db.get_recent_progress` | `GetRecentProgressTool` | 查询近期进度记录 |
| `db.get_recent_reports` | `GetRecentReportsTool` | 查询历史周报 |
| `db.get_document_list` | `GetDocumentListTool` | 查询已上传文档 |
| `vector.search_documents` | `VectorSearchTool` | 语义相似度搜索文档片段 |
| `vector.search_multi` | `MultiQuerySearchTool` | 多查询去重搜索 |
| `export.docx` | `ExportDocxTool` | 导出 Word 文档 |
| `export.markdown` | `ExportMarkdownTool` | 导出 Markdown 文件 |

### 核心工作流

**周报生成** (`POST /api/v1/reports/generate`)

```
Planner → DataCollector → ReportWriter → ReportReviewer → 保存到 MySQL
                              ↑                |
                              └── NEEDS_REVISION ──┘  (最多重试 1 次)
```

**自然语言查询** (`POST /api/v1/progress/query`)

```
Planner → DataCollector → ProgressQuery → 返回答案
```

### 层间依赖关系

```
接口层 ──→ 编排层 ──→ 规划层
                  ──→ 推理层 ──→ 模型服务层
                  ──→ 执行层 ──→ 记忆层 ──→ db/（MySQL / Milvus / Redis）
感知层 ──→ 模型服务层
      ──→ 记忆层
保障层 ──→ 横切所有层（认证、限流、异常、日志）
```

关键原则：
- **上层依赖下层，下层不依赖上层**
- **同层之间不直接依赖**（通过接口通信）
- **每层只依赖相邻的下一层接口**，不跨层调用

## Project Structure

```
app/
├── main.py                       # FastAPI 入口，启动时注册工具
├── config.py                     # Pydantic Settings 集中配置
│
├── api/                          # Layer 1: 接口层
│   ├── v1/                       #   版本化 REST API
│   │   ├── auth.py               #   认证（注册/登录）
│   │   ├── project.py            #   项目 CRUD
│   │   ├── report.py             #   周报（生成/列表/详情/导出）
│   │   ├── progress.py           #   进度（记录/列表/自然语言查询）
│   │   └── upload.py             #   文件上传
│   ├── deps.py                   #   FastAPI 依赖注入
│   └── websocket.py              #   WebSocket 流式输出
│
├── perception/                   # Layer 2: 感知层
│   ├── base.py                   #   ExtractionResult + DocumentProcessor Protocol
│   ├── pdf_processor.py          #   PDF 解析（PyMuPDF + pdfplumber）
│   ├── image_processor.py        #   图片处理（PaddleOCR + VLM）
│   ├── text_processor.py         #   文本清洗与合并
│   ├── chunker.py                #   递归分块（支持中英文）
│   └── embedder.py               #   向量化 + 写入 Milvus
│
├── agents/                       # Layer 3 + 4: 规划层 + 推理层
│   ├── state.py                  #   AgentState TypedDict（共享状态模式）
│   ├── planner/                  #   Layer 3: 规划层
│   │   ├── base.py               #     Planner Protocol
│   │   └── default_planner.py    #     默认规划器（任务类型推断）
│   ├── nodes/                    #   Layer 4: 推理层
│   │   ├── base.py               #     ReasoningNode Protocol
│   │   ├── data_collector.py     #     数据收集（通过 tool_registry 调用工具）
│   │   ├── report_writer.py      #     LLM 生成周报
│   │   ├── report_reviewer.py    #     LLM 自审核 + 修订
│   │   └── progress_query.py     #     LLM 回答自然语言问题
│   └── prompts/                  #   Prompt 模板
│       └── templates.py
│
├── orchestration/                # Layer 5: 编排层
│   ├── base.py                   #   Workflow Protocol
│   ├── router.py                 #   条件路由函数
│   ├── report_workflow.py        #   周报生成工作流（build + run + run_and_save）
│   └── query_workflow.py         #   自然语言查询工作流（build + run）
│
├── tools/                        # Layer 6: 执行层
│   ├── base.py                   #   BaseTool ABC + ToolResult
│   ├── registry.py               #   ToolRegistry 单例 + auto_discover_tools()
│   ├── db_query.py               #   MySQL 查询工具（4 个）
│   ├── vector_search.py          #   Milvus 搜索工具（2 个）
│   └── export.py                 #   文件导出工具（2 个）
│
├── memory/                       # Layer 7: 记忆层
│   ├── base.py                   #   StructuredStore / VectorStore / CacheStore Protocols
│   ├── structured.py             #   MySQL 结构化存储
│   ├── vector.py                 #   Milvus 向量存储
│   ├── cache.py                  #   Redis 缓存 + 分布式锁
│   └── unified.py                #   UnifiedMemory 统一门面
│
├── model_service/                # Layer 8: 模型服务层
│   ├── registry.py               #   ModelRegistry（运行时切换模型）
│   ├── llm.py                    #   LLM 调度（local / api / ollama）
│   ├── embedding.py              #   Embedding 调度
│   └── vlm.py                    #   VLM 调度（图片描述）
│
├── core/                         # Layer 9: 保障层
│   ├── exceptions.py             #   异常体系 + 全局处理器
│   ├── middleware.py             #   CORS / 限流 / 请求日志
│   ├── response.py               #   统一响应封装 R / PageData
│   └── security.py               #   JWT / bcrypt
│
├── models/                       # 支撑：SQLAlchemy ORM 模型
├── schemas/                      # 支撑：Pydantic 请求/响应模式
├── crud/                         # 支撑：数据访问层（Repository 模式）
├── db/                           # 支撑：数据库连接池
├── tasks/                        # 支撑：Celery 异步任务
│
├── pipeline/                     # 兼容层 → 转发到 perception/
└── services/                     # 兼容层 → 委托给 orchestration/
```

## Development

```bash
make lint    # Lint with ruff
make test    # Run tests with coverage
make fmt     # Auto-format code
```

## License

Private — Internal use only.
