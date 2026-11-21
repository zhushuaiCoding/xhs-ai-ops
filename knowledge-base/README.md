# 小红书 AI 运营长期记忆知识库（Knowledge Base）

本目录承接并升级自 `xiaohongshu-ops-skill` 的知识沉淀机制，是所有业务模块的**统一长期记忆中心**。

## 使用铁律

1. **开工前先检索**：执行选题、写稿、复刻或视觉策划前，先阅读本文件与近 14 天内的高价值记录，避免重复踩坑。
2. **完工后必沉淀**：每次账号体检、推荐流诊断、爆款复刻、发布动作与 24h/72h 复盘完成后，按类别写入结构化 Markdown（含 YAML Frontmatter）。
3. **只存可复用结论**：拒绝流水账；失效的模式将 `status` 改为 `deprecated`，不直接删除。
4. **隐私隔离策略**：`accounts/`、`topics/`、`patterns/`、`actions/`、`reviews/` 下的运行期 `.md` 文件已通过 `.gitignore` 忽略，仅在本地留存，避免账号隐私与运营数据意外提交至公开仓库。

## 目录分工

| 目录 | 存放内容 | 典型触发模块 |
| :--- | :--- | :--- |
| `accounts/` | 本号与对标账号的五维体检报告 | `xhs-research-ops` |
| `topics/` | 站外/站内筛选出的高分选题池、标题骨架、争议分歧 | `xhs-research-ops` |
| `patterns/` | 验证有效的标题模板、封面信息层级、正文节奏与评论钩子 | `xhs-research-ops` / `xhs-content-writer` / `xhs-publish-engage` |
| `actions/` | 每次发布、爆款复刻、批量评论回复的执行记录与异常熔断 | `xhs-publish-engage` |
| `reviews/` | 笔记发布后 24h/72h 数据回收与复盘归因 | `xhs-publish-engage` |

## 当前账号固定定位摘要

- **账号定位**：AI 工具实战 / Agent 工作流 / 开源项目拆解（请按需编辑 [persona.md](../config/persona.md)）
- **视觉基线**：见 [brand-visual.md](../config/brand-visual.md)
- **风控模式**：单主号稳妥模式（原生架构 Docker 安全沙箱 + Debian 官方开源 Chromium + 单一 MCP 会话）

## 高价值可复用 Pattern 索引（本地运行后持续追加）

- *（每次完成推荐流分析、账号体检或发布复盘后，将本地高频有效结论摘要索引在此）*
