# Enterprise Agent — 项目目录结构

```
agent-platform/
│
├── pyproject.toml                  # 依赖管理、构建配置 (Poetry/PDM)
├── Dockerfile                      # 多阶段构建, Python 3.11+
├── docker-compose.yml              # agent + milvus + redis + postgres
├── Makefile                        # dev/test/deploy 快捷命令
├── .env.example                    # API keys, DB URLs, feature flags
│
│
│── app/                            # ========== 应用入口 ==========
│   ├── main.py                     # FastAPI app factory, lifespan events
│   ├── api.py                      # REST endpoints: /chat, /stream, /health
│   ├── dependencies.py             # DI container, service factory
│   └── schemas.py                  # Pydantic request/response models
│
│
├── agent/                          # ========== Agent 核心 ==========
│   │
│   │── input/                      # ---- Layer 1: 输入预处理 ----
│   │   ├── __init__.py
│   │   ├── preprocessor.py         # text/image/file → 统一 Message 对象
│   │   ├── intent_router.py        # 意图分类, 路由到子 Agent
│   │   └── guardrails.py           # PII 过滤, 毒性检测, 速率限制
│   │
│   │── core/                       # ---- Layer 2: 规划与推理 (ReAct) ----
│   │   ├── agent_loop.py           # 主编排器, ReAct 循环入口
│   │   ├── planner.py              # 任务分解, DAG 构建与调度
│   │   ├── react_engine.py         # Thought → Action → Observation 循环
│   │   ├── reflector.py            # 自我反思, 错误恢复逻辑
│   │   └── state.py                # AgentState dataclass, 轮次上下文
│   │
│   │── llm/                        # ---- Layer 2.1: LLM 抽象层 ----
│   │   ├── base.py                 # BaseLLM ABC, 统一接口定义
│   │   ├── openai_provider.py      # GPT-4o / o1 适配器
│   │   ├── anthropic_provider.py   # Claude 适配器
│   │   ├── local_provider.py       # vLLM / Ollama 本地模型适配器
│   │   ├── router.py               # 模型路由, fallback chain
│   │   └── token_counter.py        # tiktoken 封装, token 预算控制
│   │
│   │── memory/                     # ---- Layer 3: 记忆系统 ----
│   │   ├── working.py              # 滑动窗口缓冲, 摘要压缩
│   │   ├── long_term.py            # 向量库 CRUD (Milvus/FAISS)
│   │   ├── retriever.py            # 语义检索, 混合检索策略
│   │   ├── knowledge_graph.py      # 实体-关系三元组存储
│   │   └── manager.py              # 写回策略, 去重, 衰减, 重要性评分
│   │
│   │── tools/                      # ---- Layer 4: 工具执行层 ----
│   │   ├── base.py                 # BaseTool ABC, JSON Schema 协议
│   │   ├── registry.py             # 动态注册, 发现, 依赖解析
│   │   ├── executor.py             # 沙箱执行, 超时, 指数退避重试
│   │   ├── builtin/                # 内置工具集
│   │   │   ├── web_search.py       #   Google/Bing/SerpAPI 封装
│   │   │   ├── code_interpreter.py #   沙箱化 Python/JS 执行
│   │   │   ├── api_caller.py       #   通用 REST/GraphQL 调用器
│   │   │   ├── file_manager.py     #   文件读写/格式转换
│   │   │   └── db_query.py         #   SQL/NoSQL 查询构建器
│   │   └── custom/                 # 用户自定义插件工具目录
│   │       └── README.md           #   插件开发指南
│   │
│   │── output/                     # ---- Layer 5: 输出后处理 ----
│   │   ├── formatter.py            # 响应合成, 引用注入, 结构化输出
│   │   ├── output_guard.py         # 幻觉检测, PII 脱敏, 合规审计
│   │   └── streaming.py            # SSE/WebSocket 流式输出
│   │
│   │── infra/                      # ---- Layer 6: 基础设施 ----
│   │   ├── tracing.py              # OpenTelemetry spans, 成本追踪
│   │   ├── metrics.py              # Prometheus counters, 延迟直方图
│   │   ├── logger.py               # structlog JSON 结构化日志
│   │   └── config.py               # pydantic-settings, 环境变量加载
│   │
│   └── prompts/                    # ---- Prompt 工程 ----
│       ├── system.py               # 系统提示词模板 (Jinja2)
│       ├── planner.py              # 任务分解提示词
│       ├── react.py                # ReAct 循环提示词模板
│       ├── reflection.py           # 自我反思提示词
│       └── few_shots/              # 示例轨迹 (JSON)
│           ├── search_example.json
│           └── code_example.json
│
│
├── tests/                          # ========== 测试 ==========
│   ├── conftest.py                 # fixtures, mock LLM, fake tools
│   ├── test_react_engine.py        # ReAct 循环单元测试
│   ├── test_tools.py               # 工具注册 & 执行器测试
│   ├── test_memory.py              # 记忆读写/衰减测试
│   └── test_e2e.py                 # 端到端对话测试
│
│
├── evals/                          # ========== 离线评估 ==========
│   ├── eval_runner.py              # 批量评估编排器
│   ├── metrics.py                  # 准确率, 延迟, 成本指标
│   └── datasets/                   # 黄金测试集 (JSONL)
│       ├── qa_golden.jsonl
│       └── tool_use_golden.jsonl
│
│
├── scripts/                        # ========== 运维脚本 ==========
│   ├── seed_knowledge.py           # 文档灌入向量库
│   └── migrate_db.py               # Alembic 数据库迁移
│
│
└── deploy/                         # ========== 部署配置 ==========
    ├── k8s/                        # Kubernetes manifests
    │   ├── deployment.yaml
    │   ├── service.yaml
    │   └── hpa.yaml                # 水平自动扩缩
    └── helm/                       # Helm chart
        ├── Chart.yaml
        ├── values.yaml
        └── templates/
```
