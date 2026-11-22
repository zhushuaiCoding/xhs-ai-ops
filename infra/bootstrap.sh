#!/usr/bin/env bash
# 一键初始化脚本（兼容包装，统一委托给跨平台 infra/ops.py）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/ops.py" bootstrap "$@"
