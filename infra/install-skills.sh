#!/usr/bin/env bash
# 注册 Skills 与 MCP 到 AI 客户端（兼容包装，统一委托给 infra/ops.py）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/ops.py" install-skills "$@"
