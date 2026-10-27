# KnowForge RAG Platform Versioning

本文件用于维护项目仓库的版本、分支和阶段开发边界，不属于公开页面内容。

## 当前正式基线

| 项目 | 值 |
| --- | --- |
| 正式交付标签 | `v1.0.4` |
| 功能冻结提交 | 以 `v1.0.4` 标签所指向提交为准 |
| 基线含义 | 多场景企业级 RAG V1.0 稳定交付维护版，包含引用式增量版本、基础治理工作台、主项目代码、讲义、章节实操代码、静态页面、测试和 Docker 部署结构 |
| 后续维护分支 | `release/1.0` |
| 后续演进分支 | `develop/2.0` |

正式交付快照以 `v1.0.4` 标签为准。`v1.0.0` 保留为首个正式交付标签，`v1.0.1` 保留为引用式增量版本并入 V1 的维护封版，`v1.0.2` 保留为基础治理工作台纳入 V1 的维护封版，`v1.0.3` 保留为 V1.0 正式封版基线，`v1.0.4` 保留为 FAQ 入库与质量门禁参数绑定修复版，`v1.0.0-phase1-baseline` 保留为早期阶段基线，不再代表当前正式交付版。

> 维护说明：引用式增量版本和基础治理工作台现已并入 V1.0 正式维护基线。后续如仍有 V1 级缺陷，
> 可以继续在 `release/1.0` 上做维护修复，并发布 `v1.0.5` 或更高维护标签。

## 长期分支

| 分支 | 用途 | 规则 |
| --- | --- | --- |
| `main` | 稳定主线 | 只保留已经验证过的交付版本和维护修复 |
| `release/1.0` | V1.0 维护线 | 只修复 V1.0 的代码、讲义、命令、Docker、测试和资料对齐问题，不加入 V2.0 新能力 |
| `develop/2.0` | V2.0 主开发线 | 基于 V1.0 稳定交付版继续开发新能力，定期接收 V1.0 维护修复 |
| `codex/v2-agent-platform` | 当前 V2.0 功能分支 | 用于搭建 V2 Agent 平台骨架与首批能力 |

历史分支 `phase1-maintenance`、`phase2-graphrag` 保留为早期阶段记录；后续常规开发以 `release/1.0` 和 `develop/2.0` 为准。

## 同步原则

V1.0 后续改动分三类处理：

| 类型 | 是否进入 `release/1.0` | 是否同步到 `develop/2.0` |
| --- | --- | --- |
| Bug 修复 | 是 | 是 |
| 命令、部署、依赖修复 | 是 | 是 |
| V1.0 根目录 `docs/`、`codealong/` | 原则上否；V1 基线缺口修正可临时解冻 | 仅随 V1 维护修复同步，不能承载 V2 新能力 |
| 示例数据、运行命令、代码注释修复 | 是 | 是 |
| V1.0 小幅体验优化 | 是 | 通常同步 |
| V2.0 新功能 | 否 | 只进入 `develop/2.0` |
| 破坏兼容性的架构调整 | 否 | 只进入 `develop/2.0`，并单独记录迁移说明 |

核心规则：**V1.0 代码修复先落在 `release/1.0`，验证通过后同步到 `main` 和 `develop/2.0`；V1.0 的 `docs/` 与 `codealong/` 默认保持冻结，只有 V1 基线缺口修正可以临时解冻并在维护标签后重新冻结；V2.0 新功能不能反向污染 V1.0。**

## V1.0 维护流程

```powershell
git checkout release/1.0
git pull origin release/1.0
```

修改完成后至少运行：

```powershell
python scripts/check_project_guardrails.py
python -m unittest discover -s tests
python scripts/course/check_codealong_alignment.py
python codealong/check_alignment.py
python -m mkdocs build
```

提交 V1.0 修复：

```powershell
git add -A
git commit -m "Fix v1.0 ..."
git push origin release/1.0
```

同步到稳定主线：

```powershell
git checkout main
git pull origin main
git merge --no-ff release/1.0
git push origin main
```

同步到 V2.0：

```powershell
git checkout develop/2.0
git pull origin develop/2.0
git merge --no-ff release/1.0
git push origin develop/2.0
```

如果 V2.0 已经大幅重构，不能直接 merge，就改用 cherry-pick：

```powershell
git checkout develop/2.0
git cherry-pick <v1_fix_commit>
git push origin develop/2.0
```

## V2.0 开发流程

V2.0 开发从 `develop/2.0` 派生功能分支：

```powershell
git checkout develop/2.0
git pull origin develop/2.0
git checkout -b feature/v2-xxx
```

功能完成并验证后合回：

```powershell
git checkout develop/2.0
git merge --no-ff feature/v2-xxx
git push origin develop/2.0
```

V2.0 未达到交付标准前，不直接合并回 `main`。到达交付标准后再创建 `release/2.0`，完成回归验证后打 `v2.0.0` 标签。

## V1.0 资料冻结

V1.0 的讲义和章节实操代码默认物理冻结：

```text
docs/
codealong/
```

V2.0 的讲义和章节实操代码必须放入独立目录：

```text
v2/docs/
v2/codealong/
```

V2.0 分支上运行冻结检查：

```powershell
python scripts/course/check_v1_freeze.py
```

如果是在 V2.0 功能开发中发现 `docs/` 或 `codealong/` 被修改，说明 V2.0 内容写错目录，需要迁移到 `v2/` 下。

当前 V1.0 重新冻结基线为 `v1.0.4`。后续如果出现 V1.0 级维护修复并需要再次解冻，
修正完成后应提交维护版本、打新标签，并用新标签作为冻结检查基线：

```powershell
python scripts/course/check_v1_freeze.py --base v1.0.4
```

## 标签规则

标签一旦推送不再移动。正式版本标签采用语义化版本：

- `v1.0.0`：V1.0 首个稳定交付版
- `v1.0.1`：V1.0 维护封版，纳入引用式增量版本
- `v1.0.2`：V1.0 维护封版，纳入基础治理工作台与运维闭环
- `v1.0.3`：V1.0 正式封版基线
- `v1.0.4`：V1.0 维护封版，修复 FAQ 入库与质量门禁参数绑定问题
- `v1.0.5` 及以上：V1.0 后续维护修复版
- `v2.0.0`：V2.0 稳定交付版

阶段标签保留为历史记录，例如：

- `v1.0.0-phase1-baseline`
- `v1.1.0-codealong-complete`

## 资料对齐规则

每次修改主项目代码时，都要判断是否需要同步：

- `docs/`、`codealong/`：V1.0 冻结目录；除 V1 基线缺口修正外不再修改。
- `v2/docs/`：V2.0 讲义是否需要更新。
- `v2/codealong/`：V2.0 章节实操代码是否需要同步。
- `site/`：讲义 HTML 是否需要重新生成。
- `README.md`、`CHANGELOG.md`、`VERSIONING.md`：仓库说明是否需要同步。
- 测试与守卫脚本：是否需要新增或调整验证用例。

V1.0 维护修复进入 `develop/2.0` 时，也要按同样规则检查资料对齐，避免 V2.0 继承过时说明；但不得改动 V1.0 已冻结的 `docs/` 和 `codealong/`。
