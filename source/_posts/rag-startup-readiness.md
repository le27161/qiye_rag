---
title: 端口打开不代表服务可用：为 RAG 设计启动与就绪检查
date: 2026-10-26 09:11:00
permalink: rag/startup-readiness/
categories: [RAG 工程]
tags: [FastAPI, Preflight, Pydantic, 配置管理]
series: RAG 工程笔记
description: 区分进程存活与业务就绪，明确基础依赖、模型预热、Schema 初始化及配置来源。
---

一个 `/health` 返回 200 的服务，仍然可能无法回答任何问题：模型目录挂错了、没有已发布知识版本，或者向量集合根本不存在。把这些问题留给第一个用户发现，并不能算完成了部署。

<!-- more -->

## 先定义“能工作”是什么意思

存活检查关注进程是否仍然运行；就绪检查关注能否承接当前业务请求。若应用把二者混成一个“永远返回 OK”的接口，网关就无法正确分流。

对 RAG，可以区分核心问答能力与治理页面。Milvus 和本地模型未就绪时，问答不应接收流量；云端模型短时不可用时，是否继续提供管理员诊断和版本查询，则可以由业务单独决定。

关键是让状态真实反映能力，而不是为了保持绿灯而静默跳过依赖。

## 启动检查顺序有依赖关系

先做便宜的静态检查：必填值、模板占位符、URI 格式和文件目录。随后检查网络与身份认证，再初始化或确认数据库 schema，然后读取 active 版本，最后预热检索栈。

TCP 端口能连接，只能证明连接建立成功，不能证明数据库认证通过或目标集合可用。更深入的检查应选择轻量、安全、不会写业务数据的操作。

active 版本检查依赖版本表存在，因此不能在 schema 尚未准备好时就读取它。首次部署还要避免循环依赖：入库任务能在 API 未就绪时独立运行，先构建初始版本，再让问答服务进入 ready。

## 模型预热必须有明确状态

把模型放进后台线程加载，不等于可以马上接收问答。预热至少要有运行中、成功和失败状态，并设定超时及失败原因。

可以在 FastAPI lifespan 中等待必要模型完成加载、执行一次真实编码并验证集合可检索。若只检查 Redis 缓存命中，可能掩盖本地模型没有真正可用的问题。

预热也应受资源预算约束。多个 worker 会分别加载本地模型，内存消耗可能随着进程数增长；扩 worker 前要先估算这一部分，而不是只看 API 的 Python 代码很轻。

## 配置入口越多，排查越困难

基础设施地址、密钥和运行模式适合由环境变量提供；业务来源、场景名称和资料规则适合放进版本化的场景配置。

下面展示 Pydantic Settings 的最小结构，需要 `pydantic-settings`：

```python
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    milvus_uri: str
    admin_token: SecretStr
    warmup_timeout_seconds: int = Field(default=120, gt=0)
```

Compose 的配置文件不是 Python 自动读取的魔法入口。使用 `--env-file` 主要影响 Compose 插值；仍需通过 `environment` 或 `env_file` 明确传入容器。应用最终读取的是容器环境，以及明确配置的本地文件。

## 数据库初始化不该藏进每个 Store

让每次创建存储对象都偷偷执行建表，会把权限、启动和请求路径混在一起。更清晰的方式，是集中维护 schema 并在受控阶段初始化。

但 `CREATE TABLE IF NOT EXISTS` 不会自动迁移已有表。生产中的字段变化仍需显式迁移、备份和兼容性策略。

启动失败应输出具体缺失项和处理方向，但不要打印 API Key、口令或完整敏感连接串。好的前置检查把故障前移，也让排查过程更安全。

延伸阅读：[Docker 交付与排障](/rag/docker-delivery/)、[基础工具与稳定 ID](/rag/fingerprints-and-foundations/)。返回 [专栏目录](/rag/)。
