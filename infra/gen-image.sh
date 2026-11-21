#!/usr/bin/env bash
# 统一图像生成调用封装（基于 baoyu-image-gen，默认使用 Google Gemini + 项目 EXTEND.md）
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

if [[ ! -f "${BAOYU_IMAGE_GEN_MAIN}" ]]; then
  echo "❌ 未找到 baoyu-image-gen 主脚本：${BAOYU_IMAGE_GEN_MAIN}"
  exit 1
fi

# 选择 bun 执行器：优先系统 bun，否则走 npx -y bun
if command -v bun >/dev/null 2>&1; then
  RUNNER=(bun)
else
  RUNNER=(npx -y bun)
fi

# 切换工作目录至项目根，使 baoyu-image-gen 稳定读取 .baoyu-skills/baoyu-image-gen/EXTEND.md
cd "${XHS_OPS_ROOT}"
exec "${RUNNER[@]}" "${BAOYU_IMAGE_GEN_MAIN}" "$@"
