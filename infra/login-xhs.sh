#!/usr/bin/env bash
# 小红书主号无界面二维码扫码登录（兼容包装，统一委托给 infra/ops.py）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/ops.py" login "$@"
