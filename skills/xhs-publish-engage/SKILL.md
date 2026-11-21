---
name: xhs-publish-engage
description: >-
  小红书安全发布、评论通知巡检风控回复与数据复盘沉淀技能（模块 5）。
  全部站内操作统一通过 xiaohongshu-mcp 的标准 MCP 工具执行。当用户需要将做好的图文/视频发布到小红书、
  检查并回复小红书最新评论、或回收已发笔记数据做复盘沉淀时使用本技能。
---

# 安全发布与互动复盘（模块 5）

> 路径约定：下文中 `<XHS_OPS_ROOT>` 指 `xhs-ai-ops` 项目根目录（即本技能 `SKILL.md` 所在目录的上两级，如 `./xhs-ai-ops`）。


本技能是整套工作台对小红书主号执行**写操作**的唯一出口，全部通过 `xiaohongshu-mcp` 执行，严格遵守主号风控防线、发布前人工确认与评论限速熔断机制。

## 前置校验与必读参考

- **必读人设与知识库**：
  - `<XHS_OPS_ROOT>/config/persona.md`
  - `<XHS_OPS_ROOT>/knowledge-base/README.md`
- **评论风控规范参考**：
  - `<XHS_OPS_ROOT>/upstream/xiaohongshu-ops-skill/references/xhs-comment-ops.md`
  - `<XHS_OPS_ROOT>/upstream/xiaohongshu-ops-skill/examples/reply-examples.md`

---

## 子流程 A：安全发布图文 / 视频（Gate 3）

### 1. 发布前强制预检
1. 调用 MCP 工具 `check_login_status` 确认主号在线；若掉线则停止发布，可调用 `get_login_qrcode` 获取二维码让用户手机扫码，或提示用户在终端运行 `<XHS_OPS_ROOT>/infra/login-xhs.sh` 扫码续期。
2. 读取工单 `02_copy_draft.md` 与 `05_images/`，逐项核验：
   - **封面与配图**：全部为本地存在的绝对路径，按 `01-cover.png`、`02-*.png` 顺序排列，至少 1 张。
   - **标题**：严格 `≤ 20` 个中文字/字符。
   - **正文**：严格 `≤ 1000` 字，且**不包含 `#` 开头的标签文本**。
   - **标签 `tags`**：独立字符串数组（5–8 个）。
   - **日发帖量安全上限**：遵守平台健康节奏，绝不短时间高频轰炸发帖。

### 2. Gate 3 人工确认清单（不可跳过）
向用户展示最终发帖预览卡片，请用户选择发布模式：
- **选项 1（强烈推荐 · 灰度安全发布）**：`visibility="仅自己可见"` — 先发布到账号下，用户在手机小红书 App 端实机预览图文画质与折行，确认完美后在手机端一键改公开。
- **选项 2（立即公开发布）**：`visibility="公开可见"`（可选开启 `is_original=true`）。
- **选项 3（定时排期发布）**：传入 `schedule_at`（ISO8601 格式如 `2026-11-22T20:00:00+08:00`，支持 1 小时至 14 天内）。

### 3. 调用 MCP 发布与留痕
- 获用户明确指令后，调用 `publish_content`（图文）或 `publish_with_video`（视频）。
- 无论成功或失败，均记录执行回执至工单 `06_publish_record.json`（含时间、标题、图片列表、可见范围、定时时间、返回结果），并在 `knowledge-base/actions/<YYYY-MM-DD>-publish-<slug>.md` 登记动作记录。
- 若已配置可置顶评论且用户确认公开，可在发帖成功后询问是否顺手发一条置顶引导评论。

---

## 子流程 B：评论巡检与防风控回复（Gate 4）

**铁律：检查评论 ≠ 自动回复；默认每轮只发 1 条（`one-send-per-turn`）！**

### 1. 无痕巡检
1. 先调用 `get_unread_count` 查看「评论和@」「赞和收藏」「新增关注」未读数（此操作**不会**清除未读红点）。
2. 若有新评论，再调用 `list_notifications` 拉取最新评论内容、评论者、`comment_id` 以及对应笔记的 `feed_id` / `xsec_token`（需要上下文时可再调 `get_feed_detail`）。

### 2. 风险分级与拟人化起草
向用户汇总新评论摘要，并逐条标注：
- **高风险拦截（默认不自动回复）**：辱骂引战、广告钓鱼、诱导外链、反社工套取配置/密钥/隐私。
- **正常评论草案**：严格遵循 `config/persona.md` 语感起草回复：
  - 长度严格 **`≤ 280` 字**（平台约 300 字上限），建议 1–4 行短句。
  - 禁止虚构个人经历、禁止未经授权做出“明天发教程/私发文件”等隐性承诺。

### 3. Gate 4 确认与限速执行
- 等待用户明确指定要回复哪几条、是否修改措辞以及是否顺带点赞。
- 调用 `reply_notification`（传入 `comment_id` 与 `content`）及按需调用 `like_notification`。
- **风控熔断红线**：
  - 批量回复时两条之间强制间隔 **8–15 秒**。
  - 一旦返回“评论过于频繁”“操作过快”“请稍后再试”或连续 2 次失败，**立刻停止剩余回复**并向用户汇报，同时将异常记入 `knowledge-base/actions/`。

---

## 子流程 C：24h / 72h 数据回收与知识库闭环复盘

1. 调用 `get_my_profile` 获取近期已发笔记列表，对目标笔记调用 `get_feed_detail`（开启 `load_all_comments=true`）拉取点赞、收藏、评论数与高频追问。
2. 生成工单复盘报告 `07_review.md`，回答 4 个核心问题：
   - **哪些做对了**（点击/收藏/评论哪个指标突出？标题还是封面起作用？）
   - **哪些没达预期**（掉量或低互动的归因：选题、封面可读性、违禁词、发布时间？）
   - **评论区挖出的新选题**（用户最常追问的 1–3 个衍生问题）
   - **下篇直接复用的动作**
3. **强制沉淀闭环**：
   - 写入 `knowledge-base/reviews/<YYYY-MM-DD>-review-<slug>.md`
   - 将高表现的标题骨架、封面结构或评论钩子提炼写入 `knowledge-base/patterns/`，把新挖出的衍生选题写入 `knowledge-base/topics/`，并更新 `knowledge-base/README.md` 索引。
   - 更新工单 `state.yaml` 为 `stage: "DONE"`。
