#!/usr/bin/env bash
# xhs-ai-ops 全链路一键健康检查脚本（Docker 隔离版）
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

PASS=0
WARN=0
FAIL=0

ok()   { echo "✅ $*"; PASS=$((PASS + 1)); }
warn() { echo "⚠️  $*"; WARN=$((WARN + 1)); }
fail() { echo "❌ $*"; FAIL=$((FAIL + 1)); }

echo "============================================================"
echo "🩺 xhs-ai-ops 小红书 AI 运营工作台 · 全链路环境体检（Docker 隔离版）"
echo "项目根目录：${XHS_OPS_ROOT}"
echo "============================================================"

echo ""
echo "[1/5] 模块 0A：站外情报采集（Agent-Reach）"
if [[ -x "${AGENT_REACH_BIN}" ]]; then
  if "${AGENT_REACH_BIN}" channels >/dev/null 2>&1; then
    ok "Agent-Reach CLI 正常（${AGENT_REACH_BIN}）"
  else
    fail "Agent-Reach CLI 执行异常"
  fi
else
  fail "未找到 Agent-Reach 虚拟环境（请先运行 ./infra/bootstrap.sh）"
fi

echo ""
echo "[2/5] 模块 0B：小红书站内总线（Docker 隔离容器 xiaohongshu-mcp）"
if [[ ! -d "${HOME}/Library/Caches/xiaohongshu-mcp" && ! -d "${XHS_OPS_ROOT}/infra/bin" ]]; then
  ok "宿主机干净：无非官方 Chromium.app 缓存与宿主机 MCP 二进制残留"
else
  warn "检测到宿主机存在旧缓存或二进制残留，建议清理：rm -rf ~/Library/Caches/xiaohongshu-mcp ${XHS_OPS_ROOT}/infra/bin"
fi

if docker info >/dev/null 2>&1; then
  ok "Docker 守护进程运行正常"
  if curl -sS --noproxy '*' --max-time 2 "http://${XHS_MCP_ADDR}/health" >/dev/null 2>&1; then
    ok "xiaohongshu-mcp 容器健康检查通过（http://${XHS_MCP_ADDR}/mcp）"
  else
    warn "xiaohongshu-mcp 容器尚未启动（可执行 ./infra/start-mcp.sh start）"
  fi
else
  warn "Docker 守护进程尚未启动（请先打开 Docker Desktop / OrbStack，再运行 ./infra/start-mcp.sh start）"
fi

if [[ -f "${COOKIES_HOST_PATH}" ]]; then
  ok "已检测到容器持久化会话文件（${COOKIES_HOST_PATH}）"
else
  warn "尚未扫码登录主号（容器启动后运行 ./infra/login-xhs.sh 或在 AI 客户端调 get_login_qrcode）"
fi

echo ""
echo "[3/5] 模块 0C：多后端生图引擎（baoyu-image-gen / 原生引擎）"
if [[ -f "${BAOYU_IMAGE_GEN_MAIN}" ]]; then
  ok "baoyu-image-gen 脚本存在"
else
  fail "缺少 baoyu-image-gen 脚本（请先运行 ./infra/bootstrap.sh）"
fi

if [[ -n "${GOOGLE_API_KEY:-}" || -n "${GEMINI_API_KEY:-}" ]]; then
  ok "已检测到 Google Gemini 密钥（默认模型：${GOOGLE_IMAGE_MODEL:-gemini-3-pro-image}；若免费层受限可自动回退内置引擎或 codex-cli）"
elif command -v codex >/dev/null 2>&1; then
  ok "已检测到本机 codex-cli，可通过 --provider codex-cli 执行参考图锚定出图"
else
  warn "未检测到 GOOGLE_API_KEY 或 codex-cli，可在 config/.env 配置或使用宿主内置生图引擎"
fi

if [[ -f "${XHS_OPS_ROOT}/.baoyu-skills/baoyu-image-gen/EXTEND.md" ]]; then
  ok "项目级生图配置 EXTEND.md 已锁定 default_provider: google, 3:4, 2k"
else
  fail "缺少 .baoyu-skills/baoyu-image-gen/EXTEND.md"
fi

echo ""
echo "[4/5] 模块 1：人设配置与知识库骨架"
for f in config/persona.md config/brand-visual.md knowledge-base/README.md; do
  if [[ -f "${XHS_OPS_ROOT}/${f}" ]]; then
    ok "文件就绪：${f}"
  else
    fail "缺少文件：${f}"
  fi
done

echo ""
echo "[5/5] AI 宿主集成状态（Skills 与 MCP）"
MCP_CFG="${HOME}/.gemini/config/mcp_config.json"
if [[ -f "${MCP_CFG}" ]] && grep -q '"xiaohongshu-mcp"' "${MCP_CFG}" 2>/dev/null; then
  ok "Antigravity MCP 配置已注册 xiaohongshu-mcp（${MCP_CFG}）"
else
  warn "Antigravity mcp_config.json 尚未注册 xiaohongshu-mcp（可运行 ./infra/install-skills.sh）"
fi

WS_SKILLS_DIR="${XHS_WORKSPACE_DIR}/.agents/skills"
GLOBAL_SKILLS_DIR="${HOME}/.gemini/config/skills"
SKILL_COUNT=0
for s in xhs-orchestrator xhs-research-ops xhs-content-writer xhs-visual-studio xhs-publish-engage; do
  if [[ -f "${WS_SKILLS_DIR}/${s}/SKILL.md" || -f "${GLOBAL_SKILLS_DIR}/${s}/SKILL.md" ]]; then
    SKILL_COUNT=$((SKILL_COUNT + 1))
  fi
done
if [[ "${SKILL_COUNT}" -eq 5 ]]; then
  ok "5 个模块化 Skills 已全部注册就绪"
else
  warn "已注册 ${SKILL_COUNT}/5 个 Skills（可运行 ./infra/install-skills.sh 补齐）"
fi

echo ""
echo "============================================================"
echo "📊 体检汇总：通过 ${PASS} 项 ｜ 待操作/警告 ${WARN} 项 ｜ 失败 ${FAIL} 项"
echo "============================================================"
if [[ "${FAIL}" -gt 0 ]]; then
  exit 1
fi
