# xhs-ai-ops · 小红书 AI 全链路模块化运营工作台

<p align="center">
  <strong>把 5 个高星开源项目去重重构，打通「站外选题 → 爆款复刻 → 双轨 3:4 锚定出图 → Docker 安全沙箱发布 → 评论风控复盘」的完整 AI Agent 工程工作台</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Architecture-6_Modules_+_4_Human_Gates-00E599?style=for-the-badge" alt="Architecture" />
  <img src="https://img.shields.io/badge/Sandbox-Native_Docker_+_Debian_Chromium-2563EB?style=for-the-badge" alt="Docker Sandbox" />
  <img src="https://img.shields.io/badge/Clients-Antigravity_%7C_Claude_%7C_Codex_%7C_OpenClaw-111827?style=for-the-badge" alt="AI Clients" />
  <img src="https://img.shields.io/badge/License-MIT-64748b?style=for-the-badge" alt="MIT License" />
</p>

---

## 一、为什么不直接拼装网传的 5 个开源项目？

市面上流传着“5 个 GitHub 神器一键自动运营小红书”的工具清单（`Agent-Reach` + `xiaohongshu-ops-skill` + `xhs-visual-director-skill` + `baoyu-xhs-images` + `xiaohongshu-mcp`）。

经过源码级实测，直接照搬全装会踩到 **4 个致命工程坑**，`xhs-ai-ops` 正是为了解决这些冲突而做的模块化重构：

| 痛点 | 直接硬拼 5 个项目 | `xhs-ai-ops` 重构解法 |
| :--- | :--- | :--- |
| **1. 主号互踢与风控** | `Agent-Reach`、`ops-skill`（CDP）与 `xiaohongshu-mcp` 三套通道都在操作小红书网页端，同登主号极易互踢限流 | **单通道收口**：`infra/reach.sh` 默认拦截小红书仅抓站外热点；站内 18 项读写、发帖与通知全部统一走 `xiaohongshu-mcp` 单会话 |
| **2. 宿主机安全隐患 & 跨架构崩溃** | 默认在宿主机下载第三方 CDN 未公证的定制 Chromium；Apple Silicon Mac 跑官方 `amd64` 镜像易触发 QEMU 崩溃 | **原生 Docker 安全沙箱**：本地构建原生 `arm64/amd64` 镜像，改用 **Debian 官方源开源 Chromium**，仅监听 `127.0.0.1`，工单图片目录**只读挂载（`:ro`）** |
| **3. 两个视觉 Skill 互相打架** | 一个强制“前置 10 问”不自带出图后端，另一个自带卡片交互确认，挂一起反复冲突 | **双轨视觉导演 + 首图锚定**：干货走快轨（`baoyu-xhs-images`），大片走精轨（`xhs-visual-director`）；先出第 1 张封面确认，再作为 `--ref` 锚定批量生成第 2–N 页，并兼容跨引擎补图 |
| **4. 缺少数据接力与人工防线** | 5 个项目出自不同作者，输入输出无统一格式，也缺乏发布与评论风控拦截 | **工单状态机 + 4 道人工关卡**：以 `workspace/posts/<date>-<slug>/` 为唯一事实来源，在选题、封面、发布（默认先发`仅自己可见`）、评论发送设 4 道强制人工确认门禁 |

---

## 二、真实成图效果展示（首图锚定 · 3:4 竖版）

以下示例全部由本工作台「精轨视觉母版 + 首图 `--ref` 锚定链」实际生成（含跨模型参考图补齐验证），零错字、手机端高可读、严格 `3:4` 竖版：

| Page 01 · 封面 | Page 03 · 重构架构 | Page 04 · 安全隔离 | Page 05 · 出图秘诀 |
| :---: | :---: | :---: | :---: |
| <img src="./docs/showcase/01-cover.jpg" width="210" alt="封面" /> | <img src="./docs/showcase/03-architecture.jpg" width="210" alt="重构架构" /> | <img src="./docs/showcase/04-docker-security.jpg" width="210" alt="Docker 安全隔离" /> | <img src="./docs/showcase/05-visual-anchor.jpg" width="210" alt="首图锚定批量出图" /> |

---

## 三、总体系统架构（六大模块 + 四道人工关卡）

```mermaid
flowchart TD
    User["创作者 (人类在环)"] --> Orch["模块 6：总控编排层 (xhs-orchestrator)"]

    subgraph Core["核心业务流水线 (skills/)"]
        M1["模块 1：账号人设与长期记忆知识库 (config/ + knowledge-base/)"]
        M2["模块 2：情报侦察与选题诊断 (xhs-research-ops)"]
        M3["模块 3：内容创作与爆款复刻 (xhs-content-writer)"]
        M4["模块 4：双轨视觉导演与出图 (xhs-visual-studio)"]
        M5["模块 5：安全发布与互动复盘 (xhs-publish-engage)"]
    end

    Orch --> M2
    M2 -->|"Gate 1：选题确认"| M3
    M3 --> M4
    M4 -->|"Gate 2：首图样张确认"| M4
    M4 -->|"Gate 3：灰度/正式发布确认"| M5
    M5 -->|"Gate 4：评论限速确认"| M5
    M5 -->|"24h/72h 复盘沉淀"| M1

    M1 -.->|"开工注入人设与历史 Pattern"| M2
    M1 -.->|"注入语感与合规红线"| M3
    M1 -.->|"注入品牌视觉令牌"| M4

    subgraph Infra["模块 0：基础设施底座 (infra/)"]
        I1["模块 0A：Agent-Reach (仅站外只读，默认屏蔽小红书)"]
        I2["模块 0B：Docker 沙箱 xiaohongshu-mcp (18 工具唯一总线)"]
        I3["模块 0C：多后端出图引擎 (Google Gemini / 原生引擎 / codex-cli)"]
    end

    M2 --> I1
    M2 --> I2
    M3 --> I2
    M4 --> I3
    M5 --> I2
```

---

## 四、模块划分与目录结构

```text
xhs-ai-ops/
├── config/                          # 模块 1：账号人设、视觉母版与环境配置模板
│   ├── persona.md                   # AI 垂类人设、内容支柱、去报告腔语感与合规红线
│   ├── brand-visual.md              # 3:4 双轨视觉母版、色板与出图策略
│   └── .env.example                 # 环境变量模板（真实 .env 自动被 .gitignore 忽略）
├── infra/                           # 模块 0：跨平台基础设施编排、Docker 安全沙箱与自检脚本
│   ├── ops.py                       # 跨平台统一运维引擎（Windows 11 / macOS / Linux 通用，纯 Python 零外部依赖）
│   ├── ops.cmd                      # Windows 便捷启动包装（PowerShell / CMD 直接调用）
│   ├── Dockerfile.arm64             # 原生架构（amd64/arm64）沙箱镜像模板（Debian 官方开源 Chromium）
│   ├── docker-compose.yml           # 仅绑定 127.0.0.1 + 工单目录只读挂载（/app/posts:ro）+ 禁提权
│   └── *.sh                         # macOS / Linux 兼容封装脚本（统一委托给 ops.py）
├── knowledge-base/                  # 模块 1：五分类长期运营记忆库（本地沉淀，自动忽略隐私文件）
│   ├── README.md                    # 总览入口与检索铁律
│   ├── accounts/                    # 账号五维体检基线
│   ├── topics/                      # 高分选题池与标题骨架
│   ├── patterns/                    # 高藏赞比爆款模式沉淀
│   ├── actions/                     # 发布与回复执行留痕
│   └── reviews/                     # 24h / 72h 数据复盘归因
├── skills/                          # 模块 2–6：五大零冲突模块化 Agent Skills
│   ├── xhs-orchestrator/            # 模块 6：总控 5 阶段状态机与 4 道人工关卡调度
│   ├── xhs-research-ops/            # 模块 2：站外热点 + 站内对标 + 账号五维体检 + 选题打分
│   ├── xhs-content-writer/          # 模块 3：原创五元组写稿 + 爆款 style-only 复刻 + 合规预审
│   ├── xhs-visual-studio/           # 模块 4：双轨视觉导演 + 母版协议 + 首图锚定批量出图
│   └── xhs-publish-engage/          # 模块 5：灰度/定时安全发布 + 通知评论风控回复 + 数据复盘
├── workspace/posts/                 # 运行期工单目录（每篇独立状态机 state.yaml + 01~07 工件）
├── docs/showcase/                   # 脱敏成图效果展示
└── upstream/                        # [gitignore] 执行 ./infra/bootstrap.sh 后自动拉取的 5 个上游仓库
```

---

## 五、3 分钟快速上手（Windows 11 / macOS / Linux 通用）

### 前置要求
- **必装**：`Git`、`Python 3.10+`、`Node.js 18+`（提供 `npx` 或装 `bun`）、`Docker`（Windows 11 安装 **Docker Desktop + WSL2 后端**；macOS 安装 Docker Desktop / OrbStack）
- **免装 Go**：若宿主机未安装 Go（或版本低于 `go.mod` 要求），`ops.py` 会自动走 Docker 多阶段容器编译，无需手动配置 Go 环境
- 任一支持 Agent Skills 与 MCP 的 AI 客户端（如 **Antigravity**、`Claude Code`、`Codex`、`OpenClaw`）

### Windows 11（PowerShell）一键部署
```powershell
git clone https://github.com/zhushuaiCoding/xhs-ai-ops.git
cd xhs-ai-ops

# 1. 拉齐 5 个上游仓库并初始化独立 .venv（Agent-Reach）
python infra/ops.py bootstrap

# 2. 启动原生 linux/amd64 安全沙箱（先打开 Docker Desktop；首次运行自动在容器内编译 Go 并装 Debian 官方 Chromium）
python infra/ops.py start

# 3. 无界面二维码扫码登录小红书主号（弹出纯 PNG 图片，手机小红书 App 扫码即可）
python infra/ops.py login

# 4. 自动注册 5 个 Skills（目录联接）与 xiaohongshu-mcp 到 Antigravity
python infra/ops.py install-skills

# 5. 全链路 13 项健康体检
python infra/ops.py doctor
```

### macOS / Linux 一键部署
```bash
git clone https://github.com/zhushuaiCoding/xhs-ai-ops.git
cd xhs-ai-ops

./infra/bootstrap.sh
./infra/start-mcp.sh start
./infra/login-xhs.sh
./infra/install-skills.sh
./infra/doctor.sh
```
> 提示：macOS / Linux 同样可以直接使用 `python3 infra/ops.py <bootstrap|start|login|install-skills|doctor>`；按需在 `config/.env`（或系统环境变量）中填写 `GOOGLE_API_KEY`，也可直接走宿主内置生图引擎或 `codex-cli`。
> ⚠️ **单主号安全铁律**：迁移到新电脑（如远程 Windows 11）扫码登录主号后，请务必停掉原电脑上的 `xhs-ai-ops-mcp` 容器（`python3 infra/ops.py stop`），避免双端网页会话互踢触发风控；日常查看主页、预览`仅自己可见`笔记请直接使用手机端 App。

---

## 六、在 AI 客户端中的日常使用范例

完成注册并重载 MCP 后，直接用自然语言对话驱动即可：

- **端到端跑一篇新笔记**：`用 xhs-orchestrator 帮我找 3 个本周 GitHub 最火的 AI Agent 选题，准备发一篇小红书图文`
- **做账号五维体检**：`用 xhs-research-ops 帮我体检一下我的小红书主号最近 10 篇笔记`
- **爆款结构复刻**：`用 xhs-content-writer 帮我按 style-only 拆解复刻这篇爆款笔记的结构：<链接或关键词>`
- **长文直出 3:4 卡片**：`用 xhs-visual-studio 把我这段技术文章做成 6 页小红书图文卡片`
- **评论无痕巡检与风控回复**：`用 xhs-publish-engage 查一下有没有新评论，先列出摘要和回复草案别直接发`
- **发布后数据复盘**：`用 xhs-publish-engage 复盘昨天发的笔记数据，并把有效模式沉淀到知识库`

---

## 七、致谢与上游开源项目

本项目为模块化编排与安全工程化整合层，核心能力建立在以下 5 个优秀开源项目之上（通过 `infra/bootstrap.sh` 按各自上游协议独立拉取，未修改上游版权声明）：

1. **[Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach)** — 多平台只读互联网检索与内容读取 CLI
2. **[xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp)** — 小红书标准 MCP Server（18 项工具与拟人化操作引擎）
3. **[Xiangyu-CAS/xiaohongshu-ops-skill](https://github.com/Xiangyu-CAS/xiaohongshu-ops-skill)** — 小红书账号诊断、推荐流分析、爆款复刻与本地知识库方法论
4. **[ziguishian/xhs-visual-director-skill](https://github.com/ziguishian/xhs-visual-director-skill)** — 24 套高级小红书视觉风格体系、统一视觉母版与反模式审查规范
5. **[JimLiu/baoyu-skills](https://github.com/JimLiu/baoyu-skills)** — `baoyu-xhs-images` 图文卡片工作流、`baoyu-image-gen` 多后端并发出图引擎与首图锚定链设计

## 八、免责声明与开源协议

- 本项目仅用于个人内容创作效率提升、技术学习与工作流研究，请严格遵守小红书平台社区规范与相关法律法规；严禁用于批量刷量、垃圾营销、搬运抄袭或未经授权的数据爬取。
- 仓库编排脚本、模块化 Skill 与文档采用 [MIT License](./LICENSE) 开源。
