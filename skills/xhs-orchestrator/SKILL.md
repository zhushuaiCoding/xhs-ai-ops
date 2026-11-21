---
name: xhs-orchestrator
description: >-
  小红书 AI 垂类全链路运营总控编排技能。当用户需要端到端完成“找选题→写稿/复刻→做封面配图→安全发布→评论复盘”完整小红书工作流，
  或需要管理、继续执行已有小红书创作工单，或需要自检 xhs-ai-ops 整体环境时使用本技能。
---

# 小红书 AI 全链路运营总控编排器（模块 6）

> 路径约定：下文中 `<XHS_OPS_ROOT>` 指 `xhs-ai-ops` 项目根目录（即本技能 `SKILL.md` 所在目录的上两级，如 `./xhs-ai-ops`）。


你负责统筹 `xhs-ai-ops` 工作台的端到端流水线，串联 5 个专业业务模块与 4 道人工确认关卡，确保账号风格统一、主号安全不触风控、中间产物可随时人工编辑与断点续跑。

## 工作台根目录与核心约定

- **项目根目录**：`<XHS_OPS_ROOT>`
- **人设配置**：`<XHS_OPS_ROOT>/config/persona.md`
- **视觉基线**：`<XHS_OPS_ROOT>/config/brand-visual.md`
- **长期知识库**：`<XHS_OPS_ROOT>/knowledge-base/README.md`
- **工单工作区**：`<XHS_OPS_ROOT>/workspace/posts/<YYYY-MM-DD>-<slug>/`

## 端到端五阶段状态机

```text
[Stage 1: RESEARCH] ──(Gate 1: 选题确认)──▶ [Stage 2: COPY] ──▶ [Stage 3: VISUAL]
                                                                       │
                                                            (Gate 2: 首图样张确认)
                                                                       ▼
[Stage 5: REVIEW] ◀──(Gate 4: 评论确认)── [Stage 4: PUBLISH] ◀──(Gate 3: 发布前确认)
```

| 阶段 | 负责模块 Skill | 关键产物 | 必须经过的人工关卡 |
| :--- | :--- | :--- | :--- |
| 1. 情报与选题 (`RESEARCH`) | `xhs-research-ops` | `01_research.md` | **Gate 1**：用户拍板 1 个最终选题或爆款 URL |
| 2. 写稿与复刻 (`COPY`) | `xhs-content-writer` | `02_copy_draft.md` | 展示标题/正文/标签与分页大纲供快速过目 |
| 3. 视觉与出图 (`VISUAL`) | `xhs-visual-studio` | `03_visual_master.md`、`04_prompts/`、`05_images/` | **Gate 2**：先出 `01-cover.png` 样图，用户确认后再批量生成第 2..N 张 |
| 4. 安全发布 (`PUBLISH`) | `xhs-publish-engage` | `06_publish_record.json` | **Gate 3**：核对三要素后，经用户明确授权再调 `publish_content`（默认推荐先发`仅自己可见`） |
| 5. 互动与复盘 (`REVIEW`) | `xhs-publish-engage` | `07_review.md` + 知识库回写 | **Gate 4**：评论回复逐条展示草案，用户确认后再发 |

## 启动新任务的强制检查顺序

1. **先读全局上下文**：阅读 `config/persona.md`、`config/brand-visual.md` 与 `knowledge-base/README.md`，避免每次从零摸索。
2. **按需体检底座**：若本次任务涉及小红书读写或生图且状态未知，可先运行：
   ```bash
   <XHS_OPS_ROOT>/infra/doctor.sh
   ```
3. **初始化工单目录与状态文件**：
   - 创建 `workspace/posts/<YYYY-MM-DD>-<slug>/`（含 `04_prompts/`、`05_images/` 子目录）。
   - 写入 `state.yaml` 追踪进度：
     ```yaml
     slug: "<YYYY-MM-DD>-<slug>"
     topic: "<主题>"
     mode: "original"          # original | viral_copy | article_to_cards
     visual_track: "auto"      # fast_cards | luxury_director | auto
     stage: "RESEARCH"         # RESEARCH | COPY | VISUAL | PUBLISH | REVIEW | DONE
     gates:
       topic_approved: false
       cover_approved: false
       publish_approved: false
     artifacts:
       research: "01_research.md"
       copy: "02_copy_draft.md"
       visual_master: "03_visual_master.md"
       images_dir: "05_images"
       publish_record: "06_publish_record.json"
       review: "07_review.md"
     ```
4. **允许单步直达与断点续跑**：
   - 如果用户已经给了现成文章/草稿要直接做图文，可跳过 Stage 1 直接写入 `02_copy_draft.md` 并进入 `xhs-visual-studio`。
   - 如果用户指定继续某个已有工单，先读该目录下的 `state.yaml` 和已有文件，尊重用户手动编辑过的 Markdown 或图片，不覆盖用户修改。

## 绝对安全红线

1. **单主号通道唯一性**：所有小红书站内读写、发帖、评论均通过 `xiaohongshu-mcp` 执行，严禁通过 `Agent-Reach` 访问小红书主号。
2. **禁止跳过确认关卡**：除用户明确写出“跳过确认 / 直接生成全套”之外，绝不在未获 Gate 2 确认时批量出图，**任何情况下绝不未经 Gate 3 确认就公开点击发布，也绝不未经 Gate 4 确认就自动回复评论**。
3. **凭据零泄露**：严禁打印、输出或写入 `GOOGLE_API_KEY`、`COOKIES_PATH` 内容或 `AUTH_TOKEN` 到任何工单、知识库或回复文本中。
