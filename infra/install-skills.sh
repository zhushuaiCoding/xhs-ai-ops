#!/usr/bin/env bash
# 将 xhs-ai-ops 的 5 个模块化 Skills 与 xiaohongshu-mcp 注册到 AI 客户端
# 用法：./infra/install-skills.sh [--scope workspace|global|both] [--target antigravity|claude|codex|openclaw|all]
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

SCOPE="both"
TARGET="antigravity"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope)  SCOPE="${2:-both}"; shift 2 ;;
    --target) TARGET="${2:-antigravity}"; shift 2 ;;
    *) echo "未知参数：$1"; exit 1 ;;
  esac
done

SKILLS=(
  "xhs-orchestrator"
  "xhs-research-ops"
  "xhs-content-writer"
  "xhs-visual-studio"
  "xhs-publish-engage"
)

link_skills_to() {
  local target_dir="$1"
  mkdir -p "${target_dir}"
  for s in "${SKILLS[@]}"; do
    local src="${XHS_OPS_ROOT}/skills/${s}"
    local dst="${target_dir}/${s}"
    if [[ ! -f "${src}/SKILL.md" ]]; then
      echo "⚠️  跳过尚未创建的技能：${s}"
      continue
    fi
    if [[ -L "${dst}" || -e "${dst}" ]]; then
      rm -rf "${dst}"
    fi
    ln -s "${src}" "${dst}"
    echo "🔗 已注册 Skill：${s} -> ${dst}"
  done
}

install_antigravity() {
  if [[ "${SCOPE}" == "workspace" || "${SCOPE}" == "both" ]]; then
    link_skills_to "${XHS_WORKSPACE_DIR}/.agents/skills"
  fi
  if [[ "${SCOPE}" == "global" || "${SCOPE}" == "both" ]]; then
    link_skills_to "${HOME}/.gemini/config/skills"
  fi

  local mcp_cfg="${HOME}/.gemini/config/mcp_config.json"
  local mcp_url="http://${XHS_MCP_ADDR}/mcp"
  mkdir -p "$(dirname "${mcp_cfg}")"

  python3 - "${mcp_cfg}" "${mcp_url}" <<'PY'
import json, os, sys
cfg_path, mcp_url = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(cfg_path) and os.path.getsize(cfg_path) > 0:
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = json.load(f)
if not isinstance(data, dict):
    data = {}
data.setdefault("mcpServers", {})["xiaohongshu-mcp"] = {"url": mcp_url}
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
print(f"✅ 已安全更新 Antigravity MCP 配置：{cfg_path} (xiaohongshu-mcp -> {mcp_url})")
PY
}

case "${TARGET}" in
  antigravity)
    install_antigravity
    ;;
  claude)
    link_skills_to "${HOME}/.claude/skills"
    ;;
  codex)
    link_skills_to "${HOME}/.codex/skills"
    ;;
  openclaw)
    link_skills_to "${HOME}/.openclaw/skills"
    ;;
  all)
    install_antigravity
    [[ -d "${HOME}/.claude" ]]   && link_skills_to "${HOME}/.claude/skills"
    [[ -d "${HOME}/.codex" ]]    && link_skills_to "${HOME}/.codex/skills"
    [[ -d "${HOME}/.openclaw" ]] && link_skills_to "${HOME}/.openclaw/skills"
    ;;
  *)
    echo "用法：$0 [--scope workspace|global|both] [--target antigravity|claude|codex|openclaw|all]"
    exit 1
    ;;
esac

echo ""
echo "🎉 集成注册完成！新开会话或重载 MCP 后即可直接使用全部 5 个技能与 18 个小红书 MCP 工具。"
