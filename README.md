# 我的 Hexo 个人博客

## 三个内容模块

首页和主导航按 RAG、Agent、大模型知识组织。专栏配置位于 `themes/aurora/_config.yml` 的 `modules`，首页文章数量与文章内的专栏返回链接使用同一配置。

- `/rag/`：21 篇已有 RAG 工程文章，路由保持不变。
- `/agent/`：6 篇 Agent 文章，以电商问数的架构、语义层、LangGraph 编排、SQL 安全与产品评测为主。
- `/llm/`：6 篇概括性文章，覆盖模型、上下文与工具、LangChain、LangGraph、应用选型及部署取舍；微调仅占选型文章中的一个短节。

新增稿件位于 `source/_posts/agent-*.md` 与 `source/_posts/llm-*.md`，目录位于 `source/agent/index.md` 与 `source/llm/index.md`。来源及参考实现与增强建议的区别见 `docs/agent-and-llm-editorial-notes.md`。

先运行 `npm run build`，再运行 `npm run check:content` 检查三个模块、页面元数据、目录覆盖和站内链接。没有运行或部署问数服务，也未修改原课件目录。

## RAG 工程笔记

新增的技术博客保存在 `source/_posts/rag-*.md`，共 21 篇，专栏目录为 `source/rag/index.md`，生成后访问 `/rag/`。这些文章参考本地 RAG 课件，按工程问题重新组织，不依赖原课件 HTML、图片或动画。

原课件目录只读取，未修改。选题、合并关系与技术处理说明见 `docs/rag-editorial-notes.md`。原有文章和已收录的独立参考页均保留。

执行 `npm run build` 构建，执行 `npm run check:rag` 检查系列文章、生成页面和站内链接。后者需要先完成构建。

## 本地运行

```powershell
npm install
npm run server
```

访问 <http://localhost:4000>。

## 发布到 GitHub Pages

1. 将 `_config.yml` 中的 `url`、`author`、GitHub 地址替换成自己的信息。
2. 将仓库推送到 `你的用户名.github.io` 的 `main` 分支。
3. 在仓库 Settings → Pages → Source 选择 **GitHub Actions**。
4. 推送后等待 Actions 完成即可访问 `https://你的用户名.github.io`。

## 开启评论

使用 Waline：部署一个 Waline 服务后，把服务地址填入 `_config.yml` 的 `theme_config.comments.serverURL`。

## 自定义域名

将 `source/CNAME.example` 复制为 `source/CNAME`，把内容改成你的域名（例如 `blog.example.com`），然后在域名 DNS 中添加 CNAME 记录指向 `你的用户名.github.io`。

## 添加已有 HTML 学习资料

完整 HTML 页面请放在 `source/prerequisites/`。它会作为独立页面发布；同时在 `source/prerequisites/index.md` 添加链接，即可从页脚的“参考资料”进入。原有链接继续保留。
