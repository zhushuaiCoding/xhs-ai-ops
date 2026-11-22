---
name: xhs-visual-studio
description: >-
  小红书 AI 垂类双轨视觉导演与批量出图引擎（模块 4）。整合 baoyu-xhs-images 快轨干货卡片、
  xhs-visual-director 精轨高级视觉导演与 baoyu-image-gen (Google Gemini 2K 3:4) 批量出图能力。
  当用户需要规划小红书封面与多页图文、生成 3:4 视觉母版和 Prompt、出图或修改单页卡片时使用本技能。
---

# 双轨视觉导演与批量出图工作室（模块 4）

> 路径约定：下文中 `<XHS_OPS_ROOT>` 指 `xhs-ai-ops` 项目根目录（即本技能 `SKILL.md` 所在目录的上两级，如 `./xhs-ai-ops`）。


本技能将 `baoyu-xhs-images` 的高效率卡片矩阵与 `xhs-visual-director-skill` 的高端设计师审美合二为一，并统一由 **Google Gemini（`baoyu-image-gen --provider google`）** 执行 3:4 / 2K 出图，兼顾“日更效率”与“封面大片高级感”。

## 开工必读与按需引用资产

- **必读配置**：
  - `<XHS_OPS_ROOT>/config/brand-visual.md`
  - 当前工单的 `02_copy_draft.md`（或用户直接提供的文章/草稿）
- **快轨参考库（按需读取，切勿一次性全读）**：
  - 风格布局矩阵与预设：`<XHS_OPS_ROOT>/upstream/baoyu-skills/skills/baoyu-xhs-images/references/style-presets.md`、`style-layout-matrix.md`
  - 单风格细则：`<XHS_OPS_ROOT>/upstream/baoyu-skills/skills/baoyu-xhs-images/references/presets/<style>.md`
  - 配色细则：`<XHS_OPS_ROOT>/upstream/baoyu-skills/skills/baoyu-xhs-images/references/palettes/<palette>.md`
- **精轨参考库（按需读取）**：
  - 24 套高级风格库：`<XHS_OPS_ROOT>/upstream/xhs-visual-director-skill/docs/style_system.md`
  - 页面节奏与母版锁定协议：`<XHS_OPS_ROOT>/upstream/xhs-visual-director-skill/docs/page_structure_rules.md`、`visual_consistency_protocol.md`
  - 反模式与审查清单：`<XHS_OPS_ROOT>/upstream/xhs-visual-director-skill/docs/anti_patterns.md`、`templates/visual_review_checklist.md`

## Step 1：智能双轨路由（化解两套风格库冲突）

根据 `02_copy_draft.md` 的内容形态与用户偏好，自动推荐最合适的视觉轨道，并在确认消息中说明理由：

1. **轨道 A · 快轨（干货卡片模式）**
   - **适用**：AI 工具清单、教程步骤、Prompt 对比、长文拆解、日常高频干货。
   - **配置维度**：从 `baoyu-xhs-images` 选择 `style`（AI 垂类默认 `notion` / `sketch-notes` / `minimal` / `study-notes`）+ `layout`（封面 `sparse`，内页 `dense` / `list` / `flow` / `comparison`）+ 可选 `palette`（默认或 `macaron` / `warm`）。
   - **交互方式**：展示推荐方案摘要（策略 / 风格 / 布局 / 页数 / 后端=Google Gemini），**1 步确认**即可进入母版与首图生成。
2. **轨道 B · 精轨（高定视觉导演模式）**
   - **适用**：AI 深度观点、Agent 架构系统拆解、重磅项目实测、追求高点击率的高级杂志封面。
   - **配置维度**：从 `xhs-visual-director` 24 套风格库中选主/辅风格（AI 垂类高频：**深色科技杂志风**、**黑白灰 + 荧光绿冲击风**、**架构图 / 系统拆解风**、**极简产品发布会风**），提供 3 套方向简述（点击优先 / 收藏优先 / 个人品牌优先）并明确推荐 1 套。
   - **交互优化（免去冗长 10 问）**：因人设、受众与核心观点已在 `config/persona.md` 与 `02_copy_draft.md` 中锁定，仅针对未明确的视觉关键决策**智能补问 3–5 题**（如深色/浅色倾向、是否有真实截图素材、期望页数 4–8 页、特别避讳的元素）；用户说“直接按推荐出图”则直接跳过补问。

## Step 2：建立统一视觉母版与逐页 Prompt 落盘

无论走轨道 A 还是轨道 B，都必须严格执行以下一致性硬约束：

1. 写入工单文件 `03_visual_master.md`，明确固化：
   - **画布锁定**：`1080x1440px, strict 3:4 vertical portrait canvas, no square, no landscape, no extra border, no crop`
   - **统一安全边距与网格**：左右 `72px`、上下 `80px`、12 列网格、固定页码/角标位置
   - **色彩与字体令牌**：固定背景色、主文色、辅助色、单一强调色及中文粗黑无衬线体风格
   - **母版锁定前缀（Master Lock Prefix）**：整套图所有页面的 Prompt 开头均须复用同一段母版锁定前缀，只在主视觉和信息结构上变化。
2. **Prompt 独立落盘（硬规则）**：
   - 调用任何生图工具前，必须先将每一页完整 Prompt（含母版锁定前缀、本页精确中文文案、布局分区、负面禁止项）写入 `04_prompts/`：
     - `04_prompts/01-cover.md`
     - `04_prompts/02-content-<slug>.md` ...
     - `04_prompts/0N-ending.md`
   - 覆盖已有 Prompt 或图片前，按备份原则保留旧版（如 `01-cover-backup-YYYYMMDD-HHMMSS.png`）。

## Step 3：首图样张验证（Gate 2 — 强制拦截点）

**铁律：未获用户确认第 1 张封面图前，严禁批量生成第 2..N 张！**（除非用户在当前指令明确写出 `--yes` / “跳过确认直接生成全套”。）

1. 先单独生成第 1 张封面（**不带 `--ref`**，以确立全套视觉锚点）：
   - **默认优先（付费 Google API，Windows / macOS / Linux 通用；macOS/Linux 若无 `python` 可用 `python3`）**：
     ```bash
     python <XHS_OPS_ROOT>/infra/ops.py gen-image \
       --provider google \
       --ar 3:4 \
       --quality 2k \
       --promptfiles "<工单目录>/04_prompts/01-cover.md" \
       --image "<工单目录>/05_images/01-cover.png"
     ```
   - **零配额自动回退（宿主原生引擎 / `codex-cli`）**：
     - 若 `GOOGLE_API_KEY` 免费层返回 `429 limit: 0`，优先无缝回退至宿主原生 `image-generator`（如 Antigravity 内置生图引擎）；
     - 若原生引擎也遇到并发配额限制，可使用本机已登录的 `codex-cli` 跨引擎补齐单页，同样完整支持 `--ref 01-cover.png` 首图锚定：
       ```bash
       python <XHS_OPS_ROOT>/infra/ops.py gen-image \
         --provider codex-cli \
         --ar 3:4 \
         --ref "<工单目录>/05_images/01-cover.png" \
         --promptfiles "<工单目录>/04_prompts/0X-page.md" \
         --image "<工单目录>/05_images/0X-page.png"
       ```
2. 生成后使用 `read_file` 查看 `05_images/01-cover.png` 进行视觉自检（反模式检查：比例是否为严格 3:4？中文字体是否清晰无乱码？是否避开廉价蓝紫渐变与 PPT 感？手机缩略图一眼能读清标题吗？）。
3. **暂停进入 Gate 2**：向用户展示封面图路径与自检结果，请用户确认：
   - **通过** → 进入 Step 4 批量出图
   - **微调** → 修改 `04_prompts/01-cover.md` 重生成封面，直到满意。

## Step 4：首图锚定批量出图（Image-1 Anchor Chain）

封面样张确认后，把 `05_images/01-cover.png` 作为**统一参考锚点（`ref`）**注入后续所有页面，锁死整套图文的色系、网格、字体和材质风格：

1. 在 `04_prompts/batch.json` 生成批量生图配置（每个 task 均带 `"ref": ["<工单目录>/05_images/01-cover.png"]`、`"provider": "google"`、`"ar": "3:4"`、`"quality": "2k"`）：
   ```json
   {
     "jobs": 4,
     "tasks": [
       {
         "id": "page-02",
         "promptFiles": ["<工单目录>/04_prompts/02-content.md"],
         "image": "<工单目录>/05_images/02-content.png",
         "ref": ["<工单目录>/05_images/01-cover.png"],
         "provider": "google",
         "ar": "3:4",
         "quality": "2k"
       }
     ]
   }
   ```
2. 执行批量并发生成（自动限流 + 单张失败自动重试 3 次，不重跑已成功页）：
   ```bash
   python <XHS_OPS_ROOT>/infra/ops.py gen-image \
     --batchfile "<工单目录>/04_prompts/batch.json" \
     --jobs 4
   ```
3. **单页返工与禁止贴字铁律**：
   - **严禁**使用 Pillow / ImageMagick / HTML / SVG 在已生成位图上强行叠加或涂抹修改文字。
   - 若某页文字渲染出错或信息过挤，仅修改该页对应 `04_prompts/0X-*.md`（可减少单页字数或优化安全区），带上 `--ref 05_images/01-cover.png` 单独重生成该页即可。

## Step 5：全套质检与交付

- 逐张核实 `05_images/*.png` 文件存在且比例均为 3:4，对照反模式清单输出简明自检结论。
- 更新 `state.yaml`（`gates.cover_approved: true`、`stage: "PUBLISH"`），汇报全部图片本地绝对路径，流转至 `xhs-publish-engage`（模块 5）。
