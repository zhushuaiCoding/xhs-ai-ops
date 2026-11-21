---
name: xhs-research-ops
description: >-
  小红书 AI 垂类情报侦察、首页推荐流分析、账号五维体检与选题量化筛选技能（模块 2）。
  当用户需要搜集 AI 站外热点（B站/YouTube/X/GitHub/V2EX/Web）、分析小红书首页推荐流、
  诊断自己或对标小红书账号表现、或生成高互动 AI 垂类选题清单时使用本技能。
---

# 情报侦察与选题诊断（模块 2）

> 路径约定：下文中 `<XHS_OPS_ROOT>` 指 `xhs-ai-ops` 项目根目录（即本技能 `SKILL.md` 所在目录的上两级，如 `./xhs-ai-ops`）。


本技能融合了 `Agent-Reach` 的跨平台情报广度与 `xiaohongshu-ops-skill` 的小红书运营分析方法论，站内数据统一通过 `xiaohongshu-mcp` 获取，避免浏览器 DOM 抓取脆弱性与多端互踢风控。

## 依赖底座与前置读取

- **开工必读**：
  - `<XHS_OPS_ROOT>/config/persona.md`
  - `<XHS_OPS_ROOT>/knowledge-base/README.md`
- **深度参考 SOP**（按具体任务按需查阅，不要一次性全加载）：
  - 首页推荐流分析框架：`<XHS_OPS_ROOT>/upstream/xiaohongshu-ops-skill/references/xhs-home-feed-analysis.md`
  - 账号五维体检标准：`<XHS_OPS_ROOT>/upstream/xiaohongshu-ops-skill/references/xhs-account-analysis.md`
  - 选题灵感与过滤标准：`<XHS_OPS_ROOT>/upstream/xiaohongshu-ops-skill/references/xhs-topic-ideation.md`
  - 知识库落库规范：`<XHS_OPS_ROOT>/upstream/xiaohongshu-ops-skill/references/xhs-knowledge-base.md`

## 数据采集双通道严格边界

1. **站外热点采集（必须走安全封装脚本）**：
   ```bash
   <XHS_OPS_ROOT>/infra/reach.sh github search "AI agent" --limit 5
   <XHS_OPS_ROOT>/infra/reach.sh bilibili search "AI 工作流" --limit 5
   <XHS_OPS_ROOT>/infra/reach.sh youtube search "AI coding workflow" --limit 5
   <XHS_OPS_ROOT>/infra/reach.sh v2ex hot --limit 10
   <XHS_OPS_ROOT>/infra/reach.sh read "<站外文章或视频链接>"
   ```
   - `infra/reach.sh` 默认拦截小红书渠道以保护主号，绝不绕过。
2. **小红书站内采集（必须走 `xiaohongshu-mcp` 工具）**：
   - 先确认会话可用：`check_login_status`（如未登录，可调 `get_login_qrcode` 获取二维码供用户扫码，或提示用户在终端运行 `<XHS_OPS_ROOT>/infra/login-xhs.sh`）。
   - 首页推荐流：`list_feeds`
   - 站内关键词检索：`search_feeds`（支持 `filters.sort_by` 如`最多点赞`/`最多收藏`/`最新`，`filters.note_type="图文"`，`filters.publish_time="一周内"`）
   - 单帖详情与高赞评论：`get_feed_detail`（传入列表返回的 `feed_id` 与 `xsec_token`）
   - 自己账号体检：`get_my_profile`
   - 竞品对标主页：`user_profile`

## 四大子工作流

### 1. 跨平台热点嗅探（AI 垂类）
- 从 GitHub / B站 / YouTube / V2EX / Web 抓取最新热门 AI 项目、工具教程与评论区分歧点。
- 提炼出“支持观点 / 反对观点 / 实操痛点”，转化为小红书用户听得懂的场景语言（避免纯学术名词堆砌）。

### 2. 首页推荐流与对标笔记分析
- 调用 `list_feeds` 或 `search_feeds` 采样 10–20 条高信号图文笔记，对其中 3–5 条代表作调 `get_feed_detail` 读取结构与评论信号。
- 输出 4 段结构化洞察：**首页/品类画像 → 3–5 条高信号样本（标题/钩子/结构/互动机制）→ 可复用模式 → 下步动作**。

### 3. 账号五维体检（本号或竞品）
- 调用 `get_my_profile` 或 `user_profile` 采样最近 9–15 篇笔记，并对 3–5 篇代表笔记调用 `get_feed_detail` 补齐评论区反馈。
- 按 5 个维度打 `1–5` 分并附原因：**定位清晰度、内容结构力、互动转化力、账号辨识度、增长可持续性**。
- 结论必须落到：**最大优势、最大短板、立刻要改的 3 条优先级动作**。
- 完成后沉淀到 `<XHS_OPS_ROOT>/knowledge-base/accounts/<YYYY-MM-DD>-<brief>.md`。

### 4. 选题量化筛选与 Gate 1 交付
- 融合“站外热点 + 站内高互动信号 + `config/persona.md` 定位”，产出 **3–5 条** 可直接进入写稿的选题。
- 每条选题必须按以下公式打分排序（总分高者优先，风险分=2 直接淘汰）：
  - 热度信号（0–2） + 账号匹配（0–2） + 互动潜力（0–2） + 可写性（0–2） - 风险分（0–2）
- 每条必须包含：**20 字内候选标题、切入角度、目标读者、核心互动钩子、三段式内容大纲、推荐视觉轨道（快轨干货卡片 / 精轨高定大片）、风险提示**。

## 产物落盘与交接

- 将完整调研与候选题清单写入当前工单：`workspace/posts/<YYYY-MM-DD>-<slug>/01_research.md`。
- 将可复用的爆款规律同步沉淀至 `knowledge-base/topics/` 或 `knowledge-base/patterns/`，并更新 `knowledge-base/README.md`。
- **在此暂停进入 Gate 1**：请用户从 3–5 条候选题中选定 1 条（或补充修改意见），确认后再交由 `xhs-content-writer` 执行模块 3。
