"""
Export the KnowForge course curriculum as an XMind mind-map file.

Usage:
    python scripts/export_xmind.py              # → knowforge-curriculum.xmind
    python scripts/export_xmind.py -o out.xmind  # custom output path
"""
import json
import zipfile
import uuid
import os
import argparse
from datetime import datetime, timezone

# ────────────────────────────────────────────────────────────
#  Course curriculum data — mirrors the HTML mindmap exactly
# ────────────────────────────────────────────────────────────

PALETTE = {
    "phase1":   "#4f46e5",
    "phase2":   "#059669",
    "phase3":   "#d97706",
    "phase4":   "#dc2626",
    "appendix": "#7c3aed",
    "anim":     "#0d9488",
}

# Shorten descriptions for XMind display (XMind nodes show less text)
TREE = {
    "id": "root",
    "title": "KnowForge RAG 系统讲义",
    "note": "19 讲 · 4 阶段 · 8 附录 · 18 动画\nLangChain + Milvus + FastAPI",
    "color": PALETTE["phase1"],
    "children": [
        # ═══ Phase 1 ═══
        {
            "id": "p1", "title": "第一阶段：基础概念",
            "note": "第 01–02 讲 · 项目概览与 RAG 核心概念",
            "color": PALETTE["phase1"],
            "children": [
                {
                    "id": "L01", "title": "第 01 讲 · 项目概述与环境搭建",
                    "note": "RAG 系统概念、技术栈全景、Docker 基础设施、开发环境配置、应用入口与启动校验",
                    "color": PALETTE["phase1"],
                    "children": [
                        {"id":"L01a","title":"RAG 应用场景","note":"企业知识库、合规审查、客服支持等场景介绍","color":PALETTE["phase1"]},
                        {"id":"L01b","title":"技术栈全景","note":"LangChain · Milvus · FastAPI · MySQL · MinIO · etcd","color":PALETTE["phase1"]},
                        {"id":"L01c","title":"Docker 基础设施","note":"docker-compose.yml 全栈编排；Milvus 2.5 · MySQL 8.4 · MinIO · etcd","color":PALETTE["phase1"]},
                        {"id":"L01d","title":"开发环境配置","note":"Settings / get_settings；.env 与 .env.compose 环境变量","color":PALETTE["phase1"]},
                        {"id":"L01e","title":"应用入口","note":"app.py · create_app()；FastAPI 启动流程","color":PALETTE["phase1"]},
                        {"id":"L01f","title":"环境前置校验","note":"validate_runtime_environment 启动验证；依赖完整性检查","color":PALETTE["phase1"]},
                    ]
                },
                {
                    "id": "L02", "title": "第 02 讲 · RAG 核心概念深入",
                    "note": "向量检索数学原理、Embedding 机制、Dense vs Sparse 检索、Reranker 作用",
                    "color": PALETTE["phase1"],
                    "children": [
                        {"id":"L02a","title":"向量检索原理","note":"余弦相似度、欧氏距离；向量空间中的最近邻搜索","color":PALETTE["phase1"]},
                        {"id":"L02b","title":"Embedding 模型","note":"get_embedding_model；BGE-M3 本地嵌入","color":PALETTE["phase1"]},
                        {"id":"L02c","title":"Dense vs Sparse","note":"稠密语义检索 vs BM25 关键词检索；优势互补与混合策略","color":PALETTE["phase1"]},
                        {"id":"L02d","title":"Reranker 重排序","note":"CrossEncoder 精排；rerank_hits 实现","color":PALETTE["phase1"]},
                        {"id":"L02e","title":"RAG 数据流全景","note":"检索→重排序→上下文构建→答案生成 (stream_query)","color":PALETTE["phase1"]},
                    ]
                },
            ]
        },
        # ═══ Phase 2 ═══
        {
            "id": "p2", "title": "第二阶段：核心 RAG 链路",
            "note": "第 03–11 讲 · LangChain → Milvus → 意图 → 检索 → 重写 → 混合搜索 → 编排 → 流水线 → 提示词",
            "color": PALETTE["phase2"],
            "children": [
                {
                    "id": "L03", "title": "第 03 讲 · LangChain 生态系统",
                    "note": "LangChain 作为「工程适配层」的角色；核心组件及其在本项目中的应用",
                    "color": PALETTE["phase2"],
                    "children": [
                        {"id":"L03a","title":"ChatOpenAI 模型适配","note":"对接 DashScope / 通义千问；统一的 LLM 调用接口","color":PALETTE["phase2"]},
                        {"id":"L03b","title":"消息模型","note":"SystemMessage · HumanMessage · AIMessage 角色分工","color":PALETTE["phase2"]},
                        {"id":"L03c","title":"结构化输出","note":"with_structured_output；意图分类 / 查询变体生成","color":PALETTE["phase2"]},
                        {"id":"L03d","title":"LangChain 组件","note":"SQLChatMessageHistory · Document · TextSplitter · Milvus VectorStore","color":PALETTE["phase2"]},
                        {"id":"L03e","title":"为何不用高层封装","note":"不使用 RetrievalQA / ConversationalRetrievalChain；保持链路可控性","color":PALETTE["phase2"]},
                    ]
                },
                {
                    "id": "L04", "title": "第 04 讲 · Milvus 索引机制",
                    "note": "向量索引本质、四种索引类型对比、PyMilvus 基本操作、langchain-milvus 对比",
                    "color": PALETTE["phase2"],
                    "children": [
                        {"id":"L04a","title":"索引本质","note":"空间换时间；构建开销 vs 查询速度的权衡","color":PALETTE["phase2"]},
                        {"id":"L04b","title":"四种索引类型","note":"FLAT · IVF_FLAT · IVF_PQ/SQ8 · HNSW","color":PALETTE["phase2"]},
                        {"id":"L04c","title":"PyMilvus 原生操作","note":"Collection 创建 · 索引构建 · 数据插入 · 向量搜索","color":PALETTE["phase2"]},
                        {"id":"L04d","title":"原生 vs langchain-milvus","note":"Hybrid Search 实现差异；存储工厂 get_faq_store / get_doc_store","color":PALETTE["phase2"]},
                    ]
                },
                {
                    "id": "L05", "title": "第 05 讲 · 意图分类",
                    "note":"规则优先 + 默认知识查询；路由直答与检索意图分层；来源推断与场景解析",
                    "color":PALETTE["phase2"],
                    "children": [
                        {"id":"L05a","title":"低成本入口策略","note":"规则优先保证确定性；不确定时默认进入知识检索","color":PALETTE["phase2"]},
                        {"id":"L05b","title":"路由与检索分层","note":"decide_route 收口直答；classify_intent 只处理检索意图","color":PALETTE["phase2"]},
                        {"id":"L05c","title":"场景解析","note":"resolve_scenario；多场景匹配与优先级","color":PALETTE["phase2"]},
                        {"id":"L05d","title":"来源检测","note":"score_source_matches；detect_source_boundary","color":PALETTE["phase2"]},
                        {"id":"L05e","title":"路由决策","note":"decide_route；FAQ 快速路径前置检查","color":PALETTE["phase2"]},
                    ]
                },
                {
                    "id": "L06", "title": "第 06 讲 · 检索策略与动态计划",
                    "note":"IntentResult → RetrievalPlan 转换；问题类型推断；参数动态调整",
                    "color":PALETTE["phase2"],
                    "children": [
                        {"id":"L06a","title":"检索计划生成","note":"build_retrieval_plan；FAQ / Doc 双通道检索编排","color":PALETTE["phase2"]},
                        {"id":"L06b","title":"问题类型推断","note":"infer_question_category；定价 · 合规 · 排障 · 总结","color":PALETTE["phase2"]},
                        {"id":"L06c","title":"表格查询检测","note":"is_table_query；结构化数据检索优化","color":PALETTE["phase2"]},
                        {"id":"L06d","title":"参数动态调整","note":"intent 调整 · short-question 调整 · risk-category 调整 · table-preference 调整","color":PALETTE["phase2"]},
                    ]
                },
                {
                    "id": "L07", "title": "第 07 讲 · 查询改写与变体生成",
                    "note":"多轮追问处理、查询改写触发条件、多角度查询变体生成与去重",
                    "color":PALETTE["phase2"],
                    "children": [
                        {"id":"L07a","title":"多轮对话处理","note":"format_messages；历史消息格式化与上下文拼接","color":PALETTE["phase2"]},
                        {"id":"L07b","title":"查询改写","note":"rewrite_query_if_needed；追问补全与指代消解","color":PALETTE["phase2"]},
                        {"id":"L07c","title":"查询变体生成","note":"generate_query_variants；LLM 变体 + 启发式变体","color":PALETTE["phase2"]},
                        {"id":"L07d","title":"去重与数量控制","note":"_heuristic_variants；变体去重 · 上限截断","color":PALETTE["phase2"]},
                    ]
                },
                {
                    "id": "L08", "title": "第 08 讲 · Milvus 混合检索",
                    "note":"Dense + BM25 Sparse 混合检索实现；Filter 表达式构建与安全校验；Reranker 融合",
                    "color":PALETTE["phase2"],
                    "children": [
                        {"id":"L08a","title":"混合检索原理","note":"Dense 语义 + BM25 关键词；双路召回 · 互补融合","color":PALETTE["phase2"]},
                        {"id":"L08b","title":"Filter 表达式","note":"Milvus 过滤条件构建；安全校验与注入防护","color":PALETTE["phase2"]},
                        {"id":"L08c","title":"双通道检索调度","note":"FAQ 通道 + Doc 通道；RetrievalPlan 并行调度","color":PALETTE["phase2"]},
                        {"id":"L08d","title":"结果合并去重","note":"多查询变体结果合并；跨通道排名融合","color":PALETTE["phase2"]},
                    ]
                },
                {
                    "id": "L09", "title": "第 09 讲 · QAService 核心编排",
                    "note":"Service Facade 模式；stream_query 与 debug_retrieval 两大核心方法",
                    "color":PALETTE["phase2"],
                    "children": [
                        {"id":"L09a","title":"编排层设计","note":"Service Facade 模式；QAService 作为统一入口","color":PALETTE["phase2"]},
                        {"id":"L09b","title":"stream_query","note":"流式问答主流程；SSE 事件推送","color":PALETTE["phase2"]},
                        {"id":"L09c","title":"debug_retrieval","note":"检索诊断接口；中间结果透出调试","color":PALETTE["phase2"]},
                        {"id":"L09d","title":"服务工厂","note":"get_qa_service；依赖注入与组件装配","color":PALETTE["phase2"]},
                        {"id":"L09e","title":"对话历史","note":"ChatHistoryStore；MySQL 持久化会话记录","color":PALETTE["phase2"]},
                    ]
                },
                {
                    "id": "L10", "title": "第 10 讲 · RAG Pipeline 主流程",
                    "note":"8 阶段事件驱动模型；FAQ 快速路径 vs 标准问答；上下文构建与引用增强",
                    "color":PALETTE["phase2"],
                    "children": [
                        {"id":"L10a","title":"8 阶段事件模型","note":"Stage 0–7 事件驱动；每阶段产出 PipelineEvent","color":PALETTE["phase2"]},
                        {"id":"L10b","title":"FAQ 双路径","note":"FAQ 快速路径（高置信直出）；FAQ 标准路径（低置信回退 RAG）","color":PALETTE["phase2"]},
                        {"id":"L10c","title":"上下文构建","note":"build_context；过滤 · 去重 · 截断策略","color":PALETTE["phase2"]},
                        {"id":"L10d","title":"引用增强","note":"答案引用标注；来源文档溯源","color":PALETTE["phase2"]},
                        {"id":"L10e","title":"流式输出终止","note":"_finish_with_single_answer；SSE 流结束信号","color":PALETTE["phase2"]},
                    ]
                },
                {
                    "id": "L11", "title": "第 11 讲 · Prompt 工程与 Profile",
                    "note":"PromptProfile 设计理念；System Prompt 编写原则；问题类型到模板的映射",
                    "color":PALETTE["phase2"],
                    "children": [
                        {"id":"L11a","title":"Profile 设计","note":"PromptProfile 结构；身份 · 边界 · 约束","color":PALETTE["phase2"]},
                        {"id":"L11b","title":"System Prompt 原则","note":"角色设定 · 能力边界 · 回答格式约束","color":PALETTE["phase2"]},
                        {"id":"L11c","title":"类型→模板映射","note":"build_answer_prompt_profile；按问题类别选择策略","color":PALETTE["phase2"]},
                        {"id":"L11d","title":"场景变量注入","note":"scenario 元数据注入提示词；动态适配不同业务场景","color":PALETTE["phase2"]},
                        {"id":"L11e","title":"诊断信息","note":"retrieval_info 调试信息；检索过程可视化","color":PALETTE["phase2"]},
                    ]
                },
            ]
        },
        # ═══ Phase 3 ═══
        {
            "id": "p3", "title": "第三阶段：Web 服务基础设施",
            "note": "第 12–13 讲 · FastAPI 异步框架 · 应用入口 · 启动前校验",
            "color": PALETTE["phase3"],
            "children": [
                {
                    "id": "L12", "title": "第 12 讲 · FastAPI 与异步 Web",
                    "note":"同步 vs 异步编程；FastAPI 路由、中间件、依赖注入；WebSocket 流式输出",
                    "color":PALETTE["phase3"],
                    "children": [
                        {"id":"L12a","title":"同步 vs 异步","note":"async/await 原理；Web 服务中的并发模型","color":PALETTE["phase3"]},
                        {"id":"L12b","title":"FastAPI 核心","note":"路由 · 中间件 · 依赖注入 (Depends)","color":PALETTE["phase3"]},
                        {"id":"L12c","title":"WebSocket 端点","note":"流式问答推送；SSE 事件格式","color":PALETTE["phase3"]},
                        {"id":"L12d","title":"API 路由层","note":"chat.py · admin.py · pages.py；请求解析与错误处理","color":PALETTE["phase3"]},
                        {"id":"L12e","title":"用户反馈","note":"FeedbackStore.add_feedback；点赞/点踩收集","color":PALETTE["phase3"]},
                    ]
                },
                {
                    "id": "L13", "title": "第 13 讲 · 应用入口与环境校验",
                    "note":"Preflight Check 设计模式；启动时依赖完整性验证；app.py 逐行解读",
                    "color":PALETTE["phase3"],
                    "children": [
                        {"id":"L13a","title":"Preflight 设计","note":"启动即验证；依赖不完整则拒绝启动","color":PALETTE["phase3"]},
                        {"id":"L13b","title":"app.py 逐行解读","note":"create_app 完整流程；从配置加载到路由注册","color":PALETTE["phase3"]},
                        {"id":"L13c","title":"值校验","note":"_is_placeholder；占位符检测 · 配置有效性","color":PALETTE["phase3"]},
                        {"id":"L13d","title":"路径校验","note":"_require_path；模型路径 · 数据目录","color":PALETTE["phase3"]},
                        {"id":"L13e","title":"运行时环境验证","note":"validate_runtime_environment；全量依赖完整性检查","color":PALETTE["phase3"]},
                    ]
                },
            ]
        },
        # ═══ Phase 4 ═══
        {
            "id": "p4", "title": "第四阶段：治理与运维",
            "note": "第 14–19 讲 · 版本管理 · 数据隔离 · 入库 · 质量 · 测试 · 可观测性",
            "color": PALETTE["phase4"],
            "children": [
                {
                    "id": "L14", "title": "第 14 讲 · 知识库多版本管理",
                    "note":"版本状态机设计；O(1) 版本切换；版本号生成与质量门禁",
                    "color":PALETTE["phase4"],
                    "children": [
                        {"id":"L14a","title":"版本状态机","note":"STAGED → ACTIVE → ARCHIVED；状态转换规则","color":PALETTE["phase4"]},
                        {"id":"L14b","title":"O(1) 切换","note":"不批量更新 Milvus；切换版本元数据指针","color":PALETTE["phase4"]},
                        {"id":"L14c","title":"版本号生成","note":"generate_kb_version；时间戳 + 配置哈希","color":PALETTE["phase4"]},
                        {"id":"L14d","title":"质量门禁","note":"Quality Report 作为版本激活前置条件","color":PALETTE["phase4"]},
                        {"id":"L14e","title":"MySQL 存储","note":"KnowledgeBaseVersionStore；版本的增删改查与激活","color":PALETTE["phase4"]},
                    ]
                },
                {
                    "id": "L15", "title": "第 15 讲 · 数据隔离与多租户",
                    "note":"DataScope 结构设计；Milvus Filter 表达式构建；轻量级多租户方案",
                    "color":PALETTE["phase4"],
                    "children": [
                        {"id":"L15a","title":"DataScope 定义","note":"tenant_id · dataset_id · visibility · user_roles","color":PALETTE["phase4"]},
                        {"id":"L15b","title":"Filter 表达式","note":"build_source_expr；安全转义 (escape_expr_value)","color":PALETTE["phase4"]},
                        {"id":"L15c","title":"数据范围解析","note":"resolve_data_scope；多维度权限计算","color":PALETTE["phase4"]},
                        {"id":"L15d","title":"结果过滤","note":"search_many 中集成过滤；检索结果按 scope 裁剪","color":PALETTE["phase4"]},
                    ]
                },
                {
                    "id": "L16", "title": "第 16 讲 · 文档入库与索引链路",
                    "note":"离线入库 vs 在线问答；文档加载/规范化/切分；IndexManifest 增量机制；FAQ CSV 入库",
                    "color":PALETTE["phase4"],
                    "children": [
                        {"id":"L16a","title":"入库编排","note":"ingest_directory；文件发现 (os.walk)","color":PALETTE["phase4"]},
                        {"id":"L16b","title":"多格式加载","note":"load_file · load_table_file；PDF · DOCX · XLSX · CSV · PPTX","color":PALETTE["phase4"]},
                        {"id":"L16c","title":"增量入库","note":"IndexManifest · file_fingerprint；stable_hash · 变更检测","color":PALETTE["phase4"]},
                        {"id":"L16d","title":"文档规范化","note":"元数据标准化 · 分块策略 · Parent-Child Chunking","color":PALETTE["phase4"]},
                        {"id":"L16e","title":"FAQ 入库","note":"FAQ CSV → Milvus；问答对向量化与写入","color":PALETTE["phase4"]},
                        {"id":"L16f","title":"引用式复用","note":"ensure_documents_validity / expire_documents_for_version；未变更文档引用复用","color":PALETTE["phase4"]},
                    ]
                },
                {
                    "id": "L17", "title": "第 17 讲 · RAG 质量评测",
                    "note":"三层质量保障体系；Gate 机制；Recall@K/MRR/关键词覆盖；Bad Case 闭环",
                    "color":PALETTE["phase4"],
                    "children": [
                        {"id":"L17a","title":"三层保障","note":"入库质量 · 检索评测 · 性能基线","color":PALETTE["phase4"]},
                        {"id":"L17b","title":"Gate 机制","note":"evaluation_gate · quality_gate · perf_gate；门禁不通过阻断","color":PALETTE["phase4"]},
                        {"id":"L17c","title":"评测指标","note":"Recall@K · MRR · 关键词覆盖率 · 命中类型","color":PALETTE["phase4"]},
                        {"id":"L17d","title":"入库质量报告","note":"build_ingestion_quality_report；FAQ 冲突检测 · Chunk 质量","color":PALETTE["phase4"]},
                        {"id":"L17e","title":"Bad Case 闭环","note":"本地报告 → eval_sets → 回归测试 → Gate 阻断退化","color":PALETTE["phase4"]},
                    ]
                },
                {
                    "id": "L18", "title": "第 18 讲 · 测试与接口验收",
                    "note":"分层测试策略；纯逻辑测试、API 保护测试、冒烟测试设计模式",
                    "color":PALETTE["phase4"],
                    "children": [
                        {"id":"L18a","title":"分层测试策略","note":"单元测试 → 门禁检查 → 冒烟测试 → 回归测试","color":PALETTE["phase4"]},
                        {"id":"L18b","title":"直调核心函数","note":"绕过 HTTP 直接调用核心链路函数进行测试","color":PALETTE["phase4"]},
                        {"id":"L18c","title":"门禁检查","note":"run_guardrails；项目级约束验证","color":PALETTE["phase4"]},
                        {"id":"L18d","title":"冒烟测试","note":"run_acceptance_smoke；核心链路端到端验证","color":PALETTE["phase4"]},
                        {"id":"L18e","title":"CI 集成","note":"非零退出码 · GitHub Actions；自动化质量门禁","color":PALETTE["phase4"]},
                    ]
                },
                {
                    "id": "L19", "title": "第 19 讲 · LangSmith 观测与部署",
                    "note":"可观测性设计；Trace 字段与元数据；生产部署、容量评估、监控告警",
                    "color":PALETTE["phase4"],
                    "children": [
                        {"id":"L19a","title":"可观测性设计","note":"为什么 RAG 系统必须有 Trace 可观测","color":PALETTE["phase4"]},
                        {"id":"L19b","title":"LangSmith 适配","note":"configure_langsmith_environment；轻量级适配器模式","color":PALETTE["phase4"]},
                        {"id":"L19c","title":"Trace 字段","note":"RAGQueryContext · 阶段计时 · run_stage · 首 token 标记","color":PALETTE["phase4"]},
                        {"id":"L19d","title":"Trace 记录","note":"record_trace；成功/失败闭合 (finish_success/finish_error)","color":PALETTE["phase4"]},
                        {"id":"L19e","title":"生产部署","note":"容量评估 · 压力测试 · 监控告警 · Docker 部署","color":PALETTE["phase4"]},
                    ]
                },
            ]
        },
        # ═══ 技术附录 ═══
        {
            "id": "appendix", "title": "技术附录 (8 篇)",
            "note": "附录 A–H · 补充知识点 · 工具链详解",
            "color": PALETTE["appendix"],
            "children": [
                {"id":"apA","title":"A · Pydantic 数据校验","note":"Settings 管理 · 类型安全；配置加载与校验模式","color":PALETTE["appendix"]},
                {"id":"apB","title":"B · SHA256 文件指纹","note":"文件去重与变更检测；stable_hash 实现","color":PALETTE["appendix"]},
                {"id":"apC","title":"C · HNSW 索引调优","note":"M · efConstruction · ef；参数选择与性能权衡","color":PALETTE["appendix"]},
                {"id":"apD","title":"D · CrossEncoder Reranker","note":"双编码器 vs 交叉编码器；BGE-Reranker-Large 原理","color":PALETTE["appendix"]},
                {"id":"apE","title":"E · Recursive Splitter","note":"RecursiveCharacterTextSplitter；语义边界感知切分","color":PALETTE["appendix"]},
                {"id":"apF","title":"F · Embedding 模型选型","note":"BGE-M3 · text2vec · OpenAI；性能对比与选型考量","color":PALETTE["appendix"]},
                {"id":"apG","title":"G · Parent-Child Chunking","note":"父子块策略；大文档结构化切分方案","color":PALETTE["appendix"]},
                {"id":"apH","title":"H · 项目工具类详解","note":"utils.py · common.py；工具函数开发实践","color":PALETTE["appendix"]},
            ]
        },
        # ═══ 动画 ═══
        {
            "id": "animations", "title": "业务流程图动画 (18 个)",
            "note": "每讲配套动画 · 综合流水线演示 · Mermaid + HTML 动画",
            "color": PALETTE["anim"],
            "children": [
                {"id":"ani1","title":"章节动画 × 18","note":"每讲功能闭环地图；节点与代码对齐动画","color":PALETTE["anim"]},
                {"id":"ani2","title":"综合流水线动画","note":"animation/business-flow.html；全链路可视化演示","color":PALETTE["anim"]},
                {"id":"ani3","title":"技术栈","note":"Mermaid.js 流程图；手写 HTML/CSS/JS 动画","color":PALETTE["anim"]},
            ]
        },
    ]
}


# ────────────────────────────────────────────────────────────
#  XMind (Zen) JSON format builder
# ────────────────────────────────────────────────────────────

def _uid():
    """生成 XMind 节点 ID。

    调用顺序：_build_topic()/build_content_json() -> _uid()。
    """
    return str(uuid.uuid4())


def _build_topic(node):
    """递归地将 TREE 节点转换为 XMind topic。

    调用顺序：build_content_json() -> _build_topic() -> _uid()。
    """
    topic = {
        "id": node.get("id", _uid()),
        "title": node.get("title", ""),
    }
    if node.get("note"):
        topic["notes"] = {
            "plain": {
                "content": node["note"],
            }
        }
    # XMind Zen supports "style" on topics — we use it for the branch color
    if node.get("color"):
        # XMind stores branch colour as a "structureClass" or via style properties.
        # The safest cross-version way is to set the `fill` on the topic style.
        topic["style"] = {
            "properties": {
                "fo:color": node["color"],
                "line-color": node["color"],
            }
        }

    children = node.get("children", [])
    if children:
        topic["children"] = {
            "attached": [_build_topic(ch) for ch in children]
        }
    return topic


def build_content_json(tree):
    """构建 XMind content.json 的单 Sheet 结构。

    调用顺序：main() -> build_content_json() -> _build_topic()。
    """
    root_topic = _build_topic(tree)
    sheet = {
        "id": _uid(),
        "title": "系统讲义",
        "rootTopic": root_topic,
    }
    return [sheet]


def build_manifest():
    """构建 XMind 压缩包内的 manifest.json 内容。

    调用顺序：命令行入口 -> build_manifest()。
    """
    return {
        "file-entries": {
            "content.json": {},
            "metadata.json": {},
        }
    }


def build_metadata():
    """构建 XMind 压缩包内的 metadata.json 内容。

    调用顺序：命令行入口 -> build_metadata()。
    """
    return {
        "creator": {
            "name": "KnowForge RAG Platform",
            "version": "1.1.0",
        },
        "created": int(datetime.now(timezone.utc).timestamp() * 1000),
    }


def write_xmind(tree, output_path):
    """Write the .xmind ZIP archive.

    调用顺序：命令行入口 -> write_xmind()。
    """
    content = build_content_json(tree)
    manifest = build_manifest()
    metadata = build_metadata()

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.json", json.dumps(content, ensure_ascii=False, indent=2))
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False))

    size_kb = os.path.getsize(output_path) / 1024
    print(f"XMind file generated: {output_path}  ({size_kb:.1f} KB)")


# ────────────────────────────────────────────────────────────
#  CLI
# ────────────────────────────────────────────────────────────

def main():
    """命令行入口：解析参数并导出课程大纲 XMind 文件。

    调用顺序：命令行入口 -> main()。
    """
    parser = argparse.ArgumentParser(description="Export KnowForge curriculum as XMind")
    parser.add_argument(
        "-o", "--output",
        default=os.path.join(os.path.dirname(__file__), "..", "knowforge-curriculum.xmind"),
        help="Output .xmind file path (default: ../knowforge-curriculum.xmind)"
    )
    args = parser.parse_args()

    out = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_xmind(TREE, out)


if __name__ == "__main__":
    main()
