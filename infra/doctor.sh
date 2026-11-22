#!/usr/bin/env bash
# xhs-ai-ops 全链路一键健康检查（兼容包装，统一委托给 infra/ops.py）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/ops.py" doctor "$@"
