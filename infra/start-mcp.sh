#!/usr/bin/env bash
# 小红书 MCP Docker 容器托管脚本：start | stop | restart | status | logs | pull
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-status}"
if [[ $# -gt 0 ]]; then
  shift
fi
exec python3 "${SCRIPT_DIR}/ops.py" "${ACTION}" "$@"
