#!/usr/bin/env bash
# 批量生图载荷构造封装（基于 baoyu-image-gen/scripts/build-batch.ts）
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

if [[ ! -f "${BAOYU_IMAGE_GEN_BATCH}" ]]; then
  echo "❌ 未找到批量构造脚本：${BAOYU_IMAGE_GEN_BATCH}"
  exit 1
fi

if command -v bun >/dev/null 2>&1; then
  RUNNER=(bun)
else
  RUNNER=(npx -y bun)
fi

cd "${XHS_OPS_ROOT}"
exec "${RUNNER[@]}" "${BAOYU_IMAGE_GEN_BATCH}" "$@"
