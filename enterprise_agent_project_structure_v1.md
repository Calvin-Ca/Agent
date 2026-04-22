  # smart-weekly-report-agent/
  │
  ├── .env.example                           # 环境变量模板 (新增)
  ├── .gitignore                             # 已修复: .env 已排除
  ├── alembic.ini                            # Alembic 迁移配置
  ├── CLAUDE.md                              # Claude Code 项目指引 (已更新)
  ├── docker-compose.yml
  ├── Dockerfile
  ├── enterprise_agent_project_structure.md   # 架构文档 (已更新)
  ├── Makefile
  ├── pyproject.toml
  ├── README.md
  │
  │
  ├── agent/                                 # ========== Agent 核心框架 ==========
  │   │
  │   ├── core/                              # ---- 规划与推理 ----
  │   │   ├── agent_loop.py                  #   主编排器: 输入→意图→规划→执行→输出
  │   │   ├── base.py                        #   Workflow/AsyncWorkflow 协议
  │   │   ├── context.py                     #   请求级 ExecutionContext + 成本追踪
  │   │   ├── errors.py                      #   Agent 异常层次
  │   │   ├── nodes.py                       #   ★ 共享工作流节点 + 路由函数 (新增,从react_engine拆出)
  │   │   ├── planner.py                     #   任务分解 + 周日期推算
  │   │   ├── react_engine.py                #   ★ 向后兼容 re-exports (重构)
  │   │   ├── reflector.py                   #   错误反思
  │   │   ├── registry.py                    #   Agent 注册表
  │   │   ├── state.py                       #   AgentState + WorkflowState
  │   │   ├── supervisor.py                  #   多 Agent 协调
  │   │   ├── checkpoint/                    #   检查点持久化
  │   │   │   ├── base.py
  │   │   │   └── redis_store.py
  │   │   └── workflows/                     #   ★ 工作流实现 (新增,从react_engine拆出)
  │   │       ├── __init__.py
  │   │       ├── query_workflow.py           #     自然语言查询 (LangGraph)
  │   │       └── report_workflow.py          #     周报生成 (LangGraph + 审核循环)
  │   │
  │   ├── input/                             # ---- 输入预处理 ----
  │   │   ├── preprocessor.py                #   PDF/图片/文本 → 统一 Message
  │   │   ├── intent_router.py               #   LLM 意图分类 + 关键字降级
  │   │   └── guardrails.py                  #   PII 过滤, 长度校验
  │   │
  │   ├── llm/                               # ---- LLM 抽象层 ----
  │   │   ├── base.py                        #   BaseLLM ABC, LLMRequest/Response
  │   │   ├── local_provider.py              #   vLLM / Ollama 本地推理
  │   │   ├── openai_provider.py             #   OpenAI API 适配器
  │   │   ├── anthropic_provider.py          #   Anthropic API 适配器
  │   │   ├── registry.py                    #   模型注册与运行时切换
  │   │   ├── router.py                      #   模型路由 + fallback chain
  │   │   └── token_counter.py               #   token 计数
  │   │
  │   ├── memory/                            # ---- 记忆系统 (6种) ----
  │   │   ├── manager.py                     #   MemoryManager 协调器
  │   │   ├── working.py                     #   滑动窗口缓冲
  │   │   ├── long_term.py                   #   Milvus 向量检索
  │   │   ├── conversation.py                #   会话历史 (TTL + token 预算)
  │   │   ├── episodic.py                    #   任务执行回忆 (成功率/质量)
  │   │   ├── summary.py                     #   轻量级摘要
  │   │   ├── knowledge_graph.py             #   实体-关系三元组
  │   │   ├── retriever.py                   #   语义检���策略
  │   │   └── base.py                        #   记忆抽象基类
  │   │
  │   ├── tools/                             # ---- 工具执行层 ----
  │   │   ├── base.py                        #   BaseTool 协议 + ToolOutput
  │   │   ├── registry.py                    #   线程安全注册 + auto_discover (已清理stub)
  │   │   ├── executor.py                    #   异步执行器 (超时+重试)
  │   │   ├── builtin/                       #   ★ 内置工具 (已清理3个stub)
  │   │   │   ├── db_query.py                #     6个数据查询工具
  │   │   │   └── file_manager.py            #     DOCX/MD导出 + MinIO视频
  │   │   └── custom/                        #   用户自定义插件
  │   │
  │   ├── output/                            # ---- 输出后处理 ----
  │   │   ├── formatter.py                   #   响应格式化
  │   │   ├── output_guard.py                #   输出安全校验
  │   │   └── streaming.py                   #   SSE 流式输出 (★ 修复循环导入)
  │   │
  │   ├── infra/                             # ---- 基础设施 ----
  │   │   ├── config.py                      #   AppSettings (pydantic-settings)
  │   │   ├── tracing.py                     #   成本追踪 + OpenTelemetry 预留
  │   │   ├── metrics.py                     #   Prometheus 指标
  │   │   ├── logger.py                      #   请求级结构化日志
  │   │   └── middleware/                    #   中间件集
  │   │       ├── logging.py
  │   │       ├── metrics.py
  │   │       ├── retry.py
  │   │       ├── streaming.py
  │   │       └── tracing.py
  │   │
  │   └── prompts/                           # ---- Prompt 工程 ----
  │       ├── system.py                      #   系统提示词
  │       ├── planner.py                     #   意图识别提示词
  │       ├── react.py                       #   周报/查询生成提示词
  │       ├── reflection.py                  #   审核提示词
  │       └── few_shots/
  │           └── query_trajectory.json
  │
  │
  ├── app/                                   # ========== 应用层 (FastAPI) ==========
  │   │
  │   ├── main.py                            #   FastAPI app factory, lifespan
  │   ├── api.py                             #   根路由聚合
  │   ├── config.py                          #   配置门面 (re-exports)
  │   ├── dependencies.py                    #   DI container (AppContainer)
  │   ├── schemas.py                         #   旧 schema 兼容
  │   │
  │   ├── api_routes/                        # ---- HTTP 路由 ----
  │   │   ├── deps.py                        #   共享依赖: DBSession, CurrentUser, Paging
  │   │   ├── websocket.py                   #   WebSocket 端点
  │   │   └── v1/
  │   │       ├── router.py                  #   V1 路由聚合 (★ 已注册6个子路由)
  │   │       ├── auth.py                    #   注册/登录/token
  │   │       ├── chat.py                    #   自然��言对话入口
  │   │       ├── projects.py                #   ★ RESTful 项目 CRUD (新增)
  │   │       ├── progress.py                #   ★ RESTful 进度记录 (新增)
  │   │       ├── reports.py                 #   ★ RESTful 周报管理 (新增)
  │   │       └── documents.py               #   ★ RESTful 文档上传 (新增)
  │   │
  │   ├── services/                          # ---- 业务逻辑 ----
  │   │   ├── chat_service.py                #   ★ 瘦身: 仅 intent 分派 (~130行,原510行)
  │   │   ├── project_service.py             #   ★ 项目 CRUD 业务 (新增)
  │   │   ├── progress_service.py            #   ★ 进度记录业务 (新增)
  │   │   ├── report_service.py              #   ★ 周报生成/查询/导出业务 (新增)
  │   │   ├── document_service.py            #   ★ 文档上传/去重/入队业务 (新增)
  │   │   └── query_service.py               #   ★ 语义查询业务 (新增)
  │   │
  │   ├── crud/                              # ---- 数据访问 (Repository) ----
  │   │   ├── base.py                        #   通用 CRUDBase 泛型基类
  │   │   ├── user.py
  │   │   ├── project.py
  │   │   ├── report.py
  │   │   └── document.py
  │   │
  │   ├── models/                            # ---- SQLAlchemy ORM ----
  │   │   ├── base.py                        #   Base (id, created_at, is_deleted)
  │   │   ├── user.py
  │   │   ├── project.py
  │   │   ├── report.py
  │   │   ├── progress.py
  │   │   └── document.py
  │   │
  │   ├── schema_defs/                       # ---- Pydantic 请求/响应 ----
  │   │   ├── user.py
  │   │   ├── project.py
  │   │   ├── report.py
  │   │   ├── progress.py
  │   │   ├── chat.py
  │   │   └── upload.py
  │   │
  │   ├── core/                              # ---- 横切关注点 ----
  │   │   ├── exceptions.py                  #   AppError > BizError > NotFoundError
  │   │   ├── response.py                    #   R<T> + PageData
  │   │   ├── security.py                    #   JWT + 密码哈希
  │   │   ├── middleware.py                  #   CORS, 请求日志
  │   │   └── resilience.py                  #   限流, 熔断
  │   │
  │   ├── db/                                # ---- 数据库连接 ----
  │   │   ├── mysql.py                       #   SQLAlchemy async engine
  │   │   ├── redis.py                       #   Redis 连接池
  │   │   ├── milvus.py                      #   Milvus 向量数据库
  │   │   └── minio.py                       #   MinIO 对象存储
  │   │
  │   └── tasks/                             # ---- Celery 异步任务 ----
  │       ├── celery_app.py
  │       ├── document_tasks.py
  │       ├── report_tasks.py
  │       └── scheduled.py
  │
  │
  ├── tests/                                 # ========== 测试 ==========
  │   ├── conftest.py                        #   fixtures, async client, JWT
  │   ├── test_nodes.py                      #   ★ 节点路由/摘要测试 (新增, 8个)
  │   ├── test_tools.py                      #   ★ 工具注册/执行测试 (扩展, 11个)
  │   ├── test_memory.py                     #   记忆系统测试 (5个)
  │   ├── test_react_engine.py               #   ReAct 循环测试
  │   ├── test_e2e.py                        #   端到端对话测试
  │   ├── test_agents/
  │   │   └── test_graph.py
  │   ├── test_api/
  │   │   ├── test_full.py
  │   │   └── test_p1.py
  │   ├── test_services/                     #   ★ 业务逻辑测试 (新增)
  │   │   ├── test_project_service.py        #     项目 API 测��� (6个)
  │   │   ├── test_progress_service.py       #     进度 API 测试 (3个)
  │   │   └── test_report_service.py         #     周报 API 测试 (3个)
  │   └── test_perception/
  │       └── test_chunker.py
  │
  │
  ├── evals/                                 # ========== 离线评估 ==========
  │   ├── eval_runner.py
  │   ├── metrics.py
  │   └── datasets/
  │       └── golden_cases.jsonl
  │
  ├── scripts/                               # ========== 运维脚本 ==========
  │   ├── init_db.py
  │   ├── init_milvus.py
  │   ├── migrate_db.py
  │   ├── mysql_init.sql
  │   ├── seed_data.py
  │   ├── seed_knowledge.py
  │   ├── benchmark_embedding.py
  │   ├── test_agent.py
  │   ├── test_connections.py
  │   └── test_models.py
  │
  ├── migrations/                            # Alembic 迁移目录
  │
  └── deploy/                                # ========== 部署配置 ==========
      ├── k8s/
      │   ├── deployment.yaml
      │   ├── service.yaml
      │   └── hpa.yaml
      └── helm/
          ├── Chart.yaml
          ├── values.yaml
          └── templates/
              └── deployment.yaml