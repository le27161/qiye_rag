---
title: async 不会自动消除阻塞：把 RAG 流式输出接进 FastAPI
date: 2026-10-26 09:10:00
permalink: rag/fastapi-streaming/
categories: [RAG 工程]
tags: [FastAPI, asyncio, WebSocket]
series: RAG 工程笔记
description: 解释同步生成器与事件循环的边界，并设计可收尾、可替换最终答案的流式事件协议。
---

接口已经写成 `async def`，一个用户提问时其他连接却一起卡住，这在 RAG 服务里并不少见。原因通常不在 WebSocket 本身，而是协程内部仍在执行同步数据库调用、本地推理，或者阻塞式模型流读取。

<!-- more -->

## async 只在真正让出执行权时有用

事件循环适合在 I/O 等待期间切换任务，但普通同步函数不会因为外层有 `async` 就自动变成非阻塞。

可以选择真正的异步客户端，也可以把已有同步流程交给工作线程。线程桥接适合平滑接入现有 SDK；本地 Embedding 和 Reranker 的吞吐问题，则可能还需要独立推理服务、批处理或进程级隔离，不能靠无限增加线程解决。

## 同步生成器要在工作线程推进

下面是一个带 WebSocket 的桥接示例。它省略了业务服务、认证、限流和完整取消机制，需要在应用中接入自己的同步事件生成器：

```python
import asyncio
from fastapi import WebSocket, WebSocketDisconnect

_END = object()

def next_event(iterator):
    return next(iterator, _END)

async def send_stream(websocket: WebSocket, iterator):
    try:
        while True:
            event = await asyncio.to_thread(next_event, iterator)
            if event is _END:
                break
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
    finally:
        close = getattr(iterator, "close", None)
        if close is not None:
            await asyncio.to_thread(close)
```

哨兵包装避免把 `StopIteration` 直接跨 Future 传播。单个迭代器只能串行推进；还要注意线程池不保证每次都在同一工作线程，具有线程亲和性的客户端需要专用线程或重新设计。

这个示例也不意味着客户端断开就能强制停止底层推理。已经运行的同步调用通常会继续执行，需要超时、协作取消，以及对外部模型流的关闭能力。

## 前后端先约定事件，而不是临时猜字段

一套实用协议可以包含开始、阶段状态、文本增量、成功终态和错误终态。每个事件带 `request_id`，必要时再带序号，便于同一连接上区分不同请求。

```json
{"type":"token","request_id":"q-42","sequence":3,"content":"请先检查证书"}
```

如果生成后会补齐引用或修订文字，成功终态应携带最终全文，前端以它替换增量草稿。错误必须说明当前文本是否只是未完成草稿，不能把半截回答当成已经核验的结果。

“一个 token 事件”也不必对应模型词表中的一个 token。网络层可以适量聚合片段，减少高频小消息的开销，但需要控制首段可见延迟。

## WebSocket 不是流式输出的唯一选择

只需要服务器单向发送文本时，SSE 或流式 HTTP 也可能合适；需要同一连接内双向控制时，WebSocket 更方便。选择取决于重连、鉴权、代理兼容和取消需求，而不是“LLM 必须用 WebSocket”。

无论哪种协议，都要处理慢客户端和背压。不能无限缓存待发送片段，也不能让断开的请求持续占用模型并发额度。

最后，普通 HTTP CORS 配置不等于 WebSocket 的 Origin 校验。长连接仍需独立的身份认证、Origin 白名单和消息级数据校验。异步解决调度问题，并不替代这些边界。

延伸阅读：[启动与就绪检查](/rag/startup-readiness/)、[容量与观测](/rag/observability-capacity/)。返回 [专栏目录](/rag/)。
