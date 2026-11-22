#!/usr/bin/env bash
# 本地构建原生架构（arm64 / amd64）Docker 沙箱镜像（兼容包装，统一委托给 infra/ops.py）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/ops.py" build-image "$@"
