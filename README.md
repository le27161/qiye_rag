# 我的 Hexo 个人博客

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
