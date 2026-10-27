如果让开发人员从 0 到 1 使用 Codex 完成一个完整 RAG 项目，提示词是：

```text
先定义项目目标和边界
→ 让 Codex 设计架构
→ 固化项目契约
→ 创建项目骨架
→ 分阶段开发
→ 每阶段测试和提交
→ 最后进行端到端验收
```

## 一、从零生成完整项目，不能只写一条提示词

不建议直接发送：

```text
请帮我从零生成一个完整企业级 RAG 项目。
```

因为“完整项目”对 Codex 来说可能意味着：

- 只生成几个 Python 文件；
- 使用假的向量检索；
- 用内存数据代替数据库；
- 不处理 Docker；
- 不处理模型加载；
- 没有测试；
- 没有版本管理；
- 接口可以启动，但业务流程不能运行。

因此，应该使用：

```text
一份总控提示词
+
多轮分阶段提示词
+
每阶段验收标准
```

总控提示词负责约束项目方向，分阶段提示词负责推动代码实现。

## 二、完整项目的总控提示词

开发人员可以在一个全新的目录中打开 Codex，例如：

```powershell
mkdir D:\workspace\knowforge-rag-greenfield
cd D:\workspace\knowforge-rag-greenfield
git init
```

然后在 Codex 中发送下面的总控提示词：

```text
当前工作区是：

D:\workspace\knowforge-rag-greenfield

这是一个从零开始的新项目，当前目录中没有可复用的业务代码。
不要假设存在任何已有模块，也不要从其他项目复制代码。

我要从零实现一个可以 Docker 部署的企业级 RAG 知识问答系统。

一、业务目标

用户输入一个业务问题，系统能够：

1. 判断问题属于哪一类业务；
2. 判断问题是否需要检索；
3. 对需要检索的问题执行 FAQ 和业务文档检索；
4. 使用 Dense + Sparse 混合检索；
5. 使用 Reranker 对候选结果进行精排；
6. 使用 LLM 根据检索证据生成答案；
7. 返回答案、来源、检索信息和阶段耗时；
8. 对问候、越界问题和高置信 FAQ 进行快速处理；
9. 支持知识库版本、数据隔离、质量检查和回归评测；
10. 支持 Docker Compose 部署。

二、技术约束

1. Python 3.12；
2. FastAPI 作为 Web 框架；
3. Milvus 2.5+ 作为向量数据库；
4. Dense 向量使用本地 BGE-M3；
5. Dense 索引使用 HNSW；
6. Sparse 使用 Milvus 服务端 BM25；
7. Sparse 字段使用 AUTOINDEX + BM25；
8. 使用 Weighted Hybrid Search 融合 Dense 和 Sparse；
9. 使用本地 BGE Reranker CrossEncoder 精排；
10. MySQL 保存会话、反馈、知识库版本和评测记录；
11. Redis 只用于 query embedding 和检索候选缓存；
12. 不缓存最终 LLM 答案；
13. 不使用 Agent；
14. 不引入 GraphRAG；
15. 使用 WebSocket 支持流式回答；
16. 使用 Docker Compose 启动 API、MySQL、Redis、etcd、MinIO 和 Milvus；
17. 本地模型通过 volume 挂载，不在镜像构建阶段下载；
18. API Key 只能从环境变量读取。

三、在线路由

在线请求只能进入以下三种路由之一：

1. direct_answer
   用于问候、越界转人工和其他无需检索的确定性回答。

2. faq_exact
   用于高置信 FAQ 命中，直接返回 FAQ 答案和来源。

3. retrieval
   用于普通知识问题，进入完整的检索、精排、上下文构建和 LLM 生成流程。

四、意图识别要求

意图识别使用以下顺序：

1. 读取对话历史；
2. 生成规则候选；
3. 对规则无法确定的问题使用意图模型校验；
4. 通过统一网关决定最终意图；
5. 根据最终意图选择 direct_answer、faq_exact 或 retrieval；
6. 记录 intent、source、score、reason 和 requires_rewrite。

五、知识库要求

支持以下知识库能力：

1. FAQ CSV 导入；
2. Markdown、TXT、PDF、DOCX、PPTX、CSV、XLSX 文档导入；
3. 文档切分；
4. FAQ 和文档分别写入 Milvus Collection；
5. 每条数据包含 source、tenant_id、dataset_id、visibility、allowed_roles 和 kb_version；
6. 知识库版本状态包括 STAGED、ACTIVE 和 ARCHIVED；
7. 只有通过质量门禁的版本才能激活；
8. 支持重新入库和失败回滚；
9. 支持文档来源和版本查询。

六、交付物要求

最终项目必须包含：

1. 应用代码；
2. Dockerfile；
3. docker-compose.yml；
4. requirements.txt；
5. .env.example；
6. 数据库初始化脚本；
7. Milvus Collection 初始化和入库脚本；
8. FAQ 和文档样例数据；
9. API 接口；
10. WebSocket 流式接口；
11. 单元测试；
12. 接口测试；
13. Smoke Test；
14. README；
15. 故障排查说明；
16. 项目架构说明；
17. 在线问答流程图；
18. 离线入库流程图；
19. 版本发布和回滚说明。

七、工作规则

1. 第一轮只分析和规划，不修改文件；
2. 后续每一轮只完成一个阶段；
3. 每次修改前先查看当前目录和 git diff；
4. 不要一次性重写整个项目；
5. 不要修改与当前阶段无关的文件；
6. 每个阶段必须有测试或可执行验收命令；
7. 每轮完成后报告修改文件、命令、结果和未完成内容；
8. 测试失败时先分析根因，再进行最小修改；
9. 不要用 mock 逻辑冒充真实 Milvus、Redis、MySQL 或模型能力；
10. 如果真实服务无法运行，必须明确区分“纯逻辑测试”和“真实集成测试”。

本轮只输出：

1. 项目总体架构；
2. 模块划分；
3. 数据库表设计；
4. Milvus Collection 设计；
5. 在线问答调用链；
6. 离线入库调用链；
7. 分阶段实施计划；
8. 每阶段验收标准；
9. 风险清单。

暂时不要创建或修改任何文件。
```

这条提示词的作用不是让 Codex 立刻写代码，而是先让它形成一份项目设计稿。

## 三、第一阶段：固化项目设计

Codex 输出方案后，继续发送：

```text
请根据刚才的方案，生成以下设计文件：

1. PROJECT_SPEC.md
2. ARCHITECTURE.md
3. API_CONTRACT.md
4. DATA_MODEL.md
5. IMPLEMENTATION_PLAN.md
6. ACCEPTANCE_CHECKLIST.md

要求：

- 明确三种在线 route；
- 明确 FAQ、Document 两类 Collection；
- 明确 text、dense、sparse 字段；
- 明确 HNSW、BM25 和 Reranker 的位置；
- 明确 MySQL、Redis、Milvus 的职责；
- 明确知识库版本状态和激活条件；
- 明确每个 API 的输入、输出和错误响应；
- 明确每个阶段将修改哪些文件；
- 不创建业务代码；
- 不生成无法验证的架构描述。

完成后停止，等待下一条指令。
```

讲课时要告诉学生：

> “从零项目最容易失败的地方，是 Codex 一开始就写代码，结果写到一半才发现数据结构、接口和模块边界没有确定。所以先让它把项目契约写出来。”

## 四、第二阶段：创建项目骨架

```text
请只实现项目骨架，不实现具体业务逻辑。

根据 PROJECT_SPEC.md 创建：

1. app.py；
2. qa_core/config；
3. qa_core/schemas；
4. qa_core/api；
5. qa_core/application；
6. qa_core/pipeline；
7. qa_core/intent；
8. qa_core/retrieval；
9. qa_core/indexing；
10. qa_core/storage；
11. qa_core/memory；
12. qa_core/quality；
13. scripts；
14. tests；
15. static；
16. scenarios。

要求：

- 所有包包含必要的 __init__.py；
- 配置统一从 .env 读取；
- 创建 GET /health；
- 暂时不连接真实数据库；
- 暂时不加载模型；
- 为配置和健康检查编写纯逻辑测试；
- 更新 README 的本地运行命令；
- 不实现检索和 LLM。

完成后执行：

python -m pytest tests -q

报告修改文件、测试结果和未完成内容。
```

验收：

```powershell
git diff
python -m pytest tests -q
git add .
git commit -m "创建项目骨架和配置"
```

## 五、第三阶段：接入基础设施

```text
请只实现 Docker Compose 和基础设施连接。

要求：

1. 启动 MySQL；
2. 启动 Redis；
3. 启动 etcd；
4. 启动 MinIO；
5. 启动 Milvus 2.5+；
6. 启动 API；
7. API 通过 Docker 服务名访问依赖；
8. 模型通过 volume 挂载；
9. API Key 使用环境变量；
10. 为 MySQL、Redis、Milvus 增加连接检查；
11. /health 返回各组件状态；
12. 不实现问答逻辑；
13. 不实现 LLM 调用。

必须验证：

docker compose config
docker compose up -d
docker compose ps
curl http://127.0.0.1:8010/health
```

这里要强调：

> “`docker compose config` 只能验证配置文件格式正确，不能证明服务可用。必须继续检查容器状态和健康接口。”

## 六、第四阶段：实现离线入库

```text
请只实现离线知识库构建流程。

调用顺序必须是：

读取资料
→ 加载为 Document
→ FAQ 转换
→ 文档切分
→ 写入 metadata
→ 创建 Milvus Collection
→ BGE-M3 生成 Dense
→ Milvus BM25 生成 Sparse
→ 写入 FAQ / Document Collection
→ 创建 STAGED 知识库版本
→ 执行质量检查
→ 质量通过后激活版本

要求：

- FAQ 和文档分别入库；
- Collection 包含 text、dense、sparse；
- Dense 使用 HNSW；
- Sparse 使用 AUTOINDEX + BM25；
- 保留 source 和 kb_version；
- 记录 tenant、dataset、visibility 和 allowed_roles；
- 质量失败时禁止激活；
- 添加入库元数据测试；
- 添加索引参数测试；
- 添加版本状态测试。

本轮不要实现在线问答。
```

入库阶段验收：

```powershell
python -m pytest tests -q
docker compose exec api python scripts/rebuild_kb.py
```

## 七、第五阶段：实现检索和 Reranker

```text
请只实现检索层，不实现意图识别和 LLM 生成。

必须实现：

1. Dense 检索；
2. BM25 Sparse 检索；
3. Weighted Hybrid Search；
4. 版本和权限过滤；
5. FAQ 与 Document 检索；
6. 多查询变体支持；
7. 结果去重；
8. BGE Reranker 精排；
9. 检索耗时统计；
10. 空候选保护。

严格顺序：

query
→ Dense + BM25 召回
→ Weighted Hybrid Search
→ 去重
→ CrossEncoder Reranker
→ top_n

要求：

- Reranker 不参与入库；
- Reranker 不替代 Milvus；
- 保留原始来源和各阶段分数；
- 不缓存最终答案；
- 为过滤、融合、去重和精排添加测试。
```

此时让学生观察：

```text
Dense 分数
BM25 分数
Hybrid 分数
Reranker 分数
```

并说明这些分数不是同一套尺度，不能直接混在一起比较。

## 八、第六阶段：实现意图和路由

```text
请只实现意图识别和三路路由，不连接 LLM。

路由必须只有：

- direct_answer；
- faq_exact；
- retrieval。

实现顺序：

读取 history
→ 规则识别
→ 规则候选
→ 模型校验
→ 网关仲裁
→ 确定最终 route
→ 生成 RetrievalPlan

要求：

- 问候进入 direct_answer；
- 越界问题进入 direct_answer；
- 高置信 FAQ 进入 faq_exact；
- 普通知识问题进入 retrieval；
- 规则结果包含 intent、score、reason 和 source；
- 模型只作为规则无法确定时的补充；
- 添加 route 决策测试；
- 不在本轮实现完整问答。
```

这一步非常关键，因为从零项目必须先固定“谁决定是否检索”，否则后面所有检索和生成逻辑都会互相调用。

## 九、第七阶段：实现完整在线问答链路

```text
请将意图、检索、Reranker、上下文和 LLM 串成完整在线问答流程。

调用顺序必须是：

请求进入
→ direct route 判断
→ active 版本读取
→ 查询改写
→ RetrievalPlan
→ FAQ 检索
→ FAQ 高分直出判断
→ 文档检索
→ FAQ + Document 合并
→ Reranker 精排
→ 上下文构建
→ LLM 生成
→ 引用补强
→ 生成后核验
→ 返回答案、来源和诊断信息

要求：

- LLM 只能看到最终上下文；
- 答案必须返回 sources；
- 没有证据时明确说明资料不足；
- 支持 WebSocket 流式事件；
- 支持 HTTP 诊断接口；
- 记录 route、intent、kb_version、retrieval、timings；
- 不缓存最终 LLM 答案；
- 为成功、空问题、无资料、LLM 失败和权限失败添加测试。
```

## 十、第八阶段：补齐治理、评测和观测

```text
请只实现企业级治理能力：

1. 知识库版本激活和回滚；
2. tenant、dataset、visibility、role 数据隔离；
3. 入库质量报告；
4. 质量门禁；
5. 回归评测；
6. Bad Case 记录；
7. Trace；
8. 阶段耗时；
9. 反馈记录；
10. 缓存版本失效。

要求：

- 质量门禁不通过时禁止激活；
- active 版本切换必须可审计；
- 缓存 Key 必须包含场景、版本和权限边界；
- 不复用最终答案缓存 Key；
- Trace 能定位一次请求经过了哪些阶段；
- 所有治理能力都要有纯逻辑测试和至少一个集成验收命令。
```

## 十一、第九阶段：最终验收和交付

```text
请对整个项目执行发布前验收，不要修改代码。

检查以下内容：

1. requirements.txt 能否在全新环境安装；
2. docker compose config 是否通过；
3. Docker 服务能否正常启动；
4. /health 是否返回正确状态；
5. FAQ 和文档能否入库；
6. Dense 和 Sparse 字段是否存在；
7. Dense 索引是否为 HNSW；
8. Sparse 是否使用 BM25；
9. 三种 route 是否都能触发；
10. Reranker 是否在召回之后执行；
11. 答案是否包含来源；
12. 无资料时是否拒绝编造；
13. 知识库版本能否激活和回滚；
14. 权限过滤是否生效；
15. Redis 缓存是否带版本边界；
16. WebSocket 是否能正常返回 end 事件；
17. 单元测试、接口测试和 Smoke Test 是否通过；
18. README 是否可以让新开发人员独立部署。

输出：

- 通过项；
- 失败项；
- 风险项；
- 需要人工验证的项目；
- 最终启动命令；
- 最终入库命令；
- 最终提问命令。

本轮不修改文件。
```

## 十二、这类提示词最重要的五个设计原则

### 1. 先写“业务行为”，再写“技术组件”

不要只写：

```text
使用 Milvus、Redis、MySQL、BGE-M3。
```

还要写：

```text
什么问题进入什么路由；
什么时候检索；
什么时候 FAQ 直出；
什么时候调用 LLM；
没有证据时如何回答；
知识库版本如何生效。
```

### 2. 每一轮必须限制修改范围

每条提示词都要有：

```text
本轮只实现什么；
本轮不实现什么；
允许修改哪些目录；
完成后执行什么测试。
```

### 3. 先让 Codex 设计，再让 Codex 写代码

推荐顺序：

```text
PROJECT_SPEC.md
→ ARCHITECTURE.md
→ API_CONTRACT.md
→ DATA_MODEL.md
→ 代码骨架
→ 模块实现
```

### 4. 每阶段都要形成证据

每一阶段至少留下：

```text
git diff
测试命令
测试结果
运行截图或接口返回
一次 git commit
```

### 5. “完整项目”必须包含可交付物

代码能运行不等于项目完成。至少还要有：

```text
环境变量模板
依赖文件
Docker 配置
数据库初始化
入库脚本
测试
健康检查
README
故障排查
发布和回滚说明
```

## 最后怎么讲给学生

可以用下面这段话收束：

> “我们现在使用的提示词，是在一个已有完整项目的基础上生成 Mini RAG，所以它会先让 Codex 阅读当前代码。真正从零开发时，不能直接让 Codex 开始写业务代码，而要先让它理解业务目标、确认架构、定义接口和数据结构。之后每次只实现一个阶段，每次都运行测试、检查 diff、提交代码。Vibe Coding 不是一次性生成，而是让 Codex 参与整个项目生命周期。”

因此，当前的 `vibe-coding-lab.md` 适合继续保留为：

```text
已有项目基础上的 Mini RAG 实践提示词
```

如果要支持“从 0 到 1 创建完整项目”，建议另外增加一份：

```text
mini-rag/prompts/codex-greenfield-enterprise-rag.md
```

两者不要混在同一份提示词中：

| 提示词 | 使用场景 |
|---|---|
| `vibe-coding-lab.md` | 基于现有 Mini RAG 或已有项目进行分阶段实现 |
| `codex-greenfield-enterprise-rag.md` | 在空目录中从需求、架构、骨架到完整项目逐步生成 |

这样学生能够清楚区分两种能力：

```text
基于已有代码使用 Codex 改造项目
从空目录使用 Codex 构建项目
```