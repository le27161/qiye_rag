# 个人技术博客

使用 Hexo 和仓库内的 Aurora 主题，记录 RAG、Agent 与大模型应用中的概念、工程取舍和学习笔记。

站点：<https://le27161.github.io>

## 本地开发

需要 Node.js 20 或更高版本。

```sh
npm ci
npm run server
```

访问 <http://localhost:4000>。

## 构建与检查

```sh
npm run clean
npm run build
npm run check:content
```

检查覆盖三个专栏的文章元数据、目录、生成页面和站内链接，不代表文章中的外部系统已完成运行验证。

## 目录

- `source/_posts/`：博客文章。
- `source/rag/`、`source/agent/`、`source/llm/`：专栏目录。
- `themes/aurora/`：主题布局、样式和导航配置。
- `tools/`：内容检查脚本。
- `docs/`：资料来源、编辑说明与验证边界。

学习资料的来源与使用说明见 [RAG 系列说明](docs/rag-editorial-notes.md) 和 [Agent 与大模型知识说明](docs/agent-and-llm-editorial-notes.md)。不随仓库分发授权状态未核实的课件原页及配套资源。

## GitHub Pages

将源码推送至 `le27161/le27161.github.io` 的 `main` 分支，在仓库 **Settings → Pages → Source** 选择 **GitHub Actions**。工作流会安装依赖、构建、检查并发布 `public/`。

`node_modules/`、`public/`、`db.json`、`work/` 和本地环境变量文件已忽略，不应提交。上传源码时保留 `package-lock.json`。

如果使用其他账号或项目仓库，请同步修改 `_config.yml` 中的 `url`、`root`、`author` 和 GitHub 链接。

## 可选配置

- 评论默认关闭。启用 Waline 前，在 `_config.yml` 中填写 `theme_config.comments.serverURL` 并将 `enable` 设为 `true`。
- 使用自定义域名时，将 `source/CNAME.example` 复制为 `source/CNAME`，填写域名并配置 DNS。
