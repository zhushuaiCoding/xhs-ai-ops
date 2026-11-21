#!/usr/bin/env bash
# Agent-Reach 站外情报采集安全封装
# 单主号稳妥模式：默认拦截 xiaohongshu 渠道，防止与 xiaohongshu-mcp 发生主号登录态互踢
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

if [[ ! -x "${AGENT_REACH_BIN}" ]]; then
  echo "❌ 未找到 Agent-Reach 可执行文件：${AGENT_REACH_BIN}"
  exit 1
fi

# 拦截直接调用 xiaohongshu 渠道或传入小红书链接（除非显式声明已隔离小号）
if [[ "${ALLOW_REACH_XHS:-0}" != "1" ]]; then
  for arg in "$@"; do
    case "$arg" in
      xiaohongshu|*xiaohongshu.com*|*xhslink.com*)
        echo "⛔ [风控保护] 当前为单主号稳妥模式，已拦截 Agent-Reach 访问小红书渠道。"
        echo "👉 小红书站内检索、详情与推荐流请统一使用 xiaohongshu-mcp（search_feeds / list_feeds / get_feed_detail）。"
        echo "👉 若已配置独立采集小号，请显式传入 ALLOW_REACH_XHS=1 后重试。"
        exit 2
        ;;
    esac
  done
fi

# 修复 macOS Python 3.13 缺失系统根证书问题：显式指向虚拟环境内 certifi CA 证书包
if [[ -z "${SSL_CERT_FILE:-}" && -x "${XHS_OPS_ROOT}/.venv/bin/python" ]]; then
  CERT_PATH="$("${XHS_OPS_ROOT}/.venv/bin/python" -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
  if [[ -n "${CERT_PATH}" && -f "${CERT_PATH}" ]]; then
    export SSL_CERT_FILE="${CERT_PATH}"
    export REQUESTS_CA_BUNDLE="${CERT_PATH}"
  fi
fi

exec "${AGENT_REACH_BIN}" "$@"
