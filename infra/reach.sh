#!/usr/bin/env bash
# Agent-Reach 站外情报采集安全封装（兼容包装，统一委托给 infra/ops.py）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/ops.py" reach "$@"
