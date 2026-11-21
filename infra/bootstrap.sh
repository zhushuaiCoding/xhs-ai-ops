#!/usr/bin/env bash
# 一键初始化脚本：拉取 5 个上游开源仓库至 upstream/，并安装 Agent-Reach 虚拟环境
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

UPSTREAM_DIR="${XHS_OPS_ROOT}/upstream"
mkdir -p "${UPSTREAM_DIR}" \
  "${XHS_OPS_ROOT}/knowledge-base/accounts" \
  "${XHS_OPS_ROOT}/knowledge-base/topics" \
  "${XHS_OPS_ROOT}/knowledge-base/patterns" \
  "${XHS_OPS_ROOT}/knowledge-base/actions" \
  "${XHS_OPS_ROOT}/knowledge-base/reviews" \
  "${XHS_OPS_ROOT}/workspace/posts"

clone_or_update() {
  local name="$1"
  local url="$2"
  local dst="${UPSTREAM_DIR}/${name}"
  if [[ -d "${dst}/.git" ]]; then
    echo "✅ 已存在上游仓库：${name}（如需更新请手动在该目录执行 git pull）"
    return 0
  fi
  echo "⬇️  正在拉取 ${name} (${url}) ..."
  git clone --depth 1 "${url}" "${dst}"
}

echo "============================================================"
echo "🚀 xhs-ai-ops 一键初始化（拉取 5 个上游开源底座）"
echo "项目目录：${XHS_OPS_ROOT}"
echo "============================================================"

clone_or_update "Agent-Reach" "https://github.com/Panniantong/Agent-Reach.git"
clone_or_update "xiaohongshu-ops-skill" "https://github.com/Xiangyu-CAS/xiaohongshu-ops-skill.git"
clone_or_update "xhs-visual-director-skill" "https://github.com/ziguishian/xhs-visual-director-skill.git"
clone_or_update "baoyu-skills" "https://github.com/JimLiu/baoyu-skills.git"

# xiaohongshu-mcp 含较大演示 GIF，默认跳过 assets/ 加速克隆且保留全部可编译源码
if [[ -d "${UPSTREAM_DIR}/xiaohongshu-mcp/.git" ]]; then
  echo "✅ 已存在上游仓库：xiaohongshu-mcp"
else
  echo "⬇️  正在拉取 xiaohongshu-mcp（跳过演示大动图加速检出源码）..."
  git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 clone \
    --depth 1 --filter=blob:limit=2m --no-checkout \
    "https://github.com/xpzouying/xiaohongshu-mcp.git" "${UPSTREAM_DIR}/xiaohongshu-mcp"
  (
    cd "${UPSTREAM_DIR}/xiaohongshu-mcp"
    git sparse-checkout init --no-cone
    printf '/*\n!/assets/\n' > .git/info/sparse-checkout
    git checkout
  )
fi

echo ""
echo "🐍 正在初始化项目独立 Python 虚拟环境并安装 Agent-Reach..."
if [[ ! -x "${XHS_OPS_ROOT}/.venv/bin/python" ]]; then
  python3 -m venv "${XHS_OPS_ROOT}/.venv"
fi
"${XHS_OPS_ROOT}/.venv/bin/pip" install -q --upgrade pip
"${XHS_OPS_ROOT}/.venv/bin/pip" install -q -e "${UPSTREAM_DIR}/Agent-Reach"
echo "✅ Agent-Reach 安装完成：${AGENT_REACH_BIN}"

if [[ ! -f "${XHS_OPS_ROOT}/config/.env" ]]; then
  cp "${XHS_OPS_ROOT}/config/.env.example" "${XHS_OPS_ROOT}/config/.env"
  echo "📝 已生成本地配置模板：config/.env（请按需填入 API Key）"
fi

echo ""
echo "============================================================"
echo "🎉 初始化完成！接下来执行以下 3 步即可开始使用："
echo "   1. 打开 Docker Desktop，运行：./infra/start-mcp.sh start"
echo "   2. 扫码登录小红书主号：./infra/login-xhs.sh"
echo "   3. 注册 Skills 与 MCP 到 AI 客户端：./infra/install-skills.sh"
echo "   4. 一键环境体检：./infra/doctor.sh"
echo "============================================================"
