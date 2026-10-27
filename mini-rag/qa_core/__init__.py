"""Mini RAG 核心包 — 提供完整 RAG 在线问答所必需的所有模块。

模块职责一览：
  - config.py   : 场景配置、Settings 设置、环境变量读取
  - models.py   : Embedding / Reranker / ChatModel 模型加载与缓存
  - retrieval.py: Milvus 混合检索封装（Dense + BM25 Sparse + Reranker）
  - query.py    : 追问改写 + 查询变体生成
  - schemas.py  : 数据对象定义（RetrievalPlan / QueryPreparation / AnswerResult 等）
  - prompts.py  : System Prompt 构建 + LLM 答案生成
  - pipeline.py : RAG 主流程编排（ask 函数入口）
  - ingest.py   : FAQ / 文档入库与知识库重建
  - loaders.py  : 多格式文档加载器 + 文本切分
  - kb_version.py: MySQL 知识库版本管理（建表、创建、激活、查询）
  - runtime.py  : 运行时依赖检查与友好报错
"""


