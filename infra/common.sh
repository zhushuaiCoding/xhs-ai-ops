#!/usr/bin/env bash
# 公共环境变量与路径解析脚本（跨平台便携 · Docker 隔离版）

XHS_OPS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export XHS_OPS_ROOT
export XHS_WORKSPACE_DIR="${XHS_WORKSPACE_DIR:-$(cd "${XHS_OPS_ROOT}/.." && pwd)}"

# 自动探测宿主机架构，用于原生 Docker 镜像构建（规避 QEMU 跨架构模拟崩溃）
RAW_ARCH="$(uname -m)"
case "${RAW_ARCH}" in
  arm64|aarch64)
    DEFAULT_GOARCH="arm64"
    DEFAULT_DOCKER_PLATFORM="linux/arm64"
    DEFAULT_IMAGE_TAG="xhs-ai-ops-mcp:arm64"
    ;;
  x86_64|amd64)
    DEFAULT_GOARCH="amd64"
    DEFAULT_DOCKER_PLATFORM="linux/amd64"
    DEFAULT_IMAGE_TAG="xhs-ai-ops-mcp:amd64"
    ;;
  *)
    DEFAULT_GOARCH="amd64"
    DEFAULT_DOCKER_PLATFORM="linux/amd64"
    DEFAULT_IMAGE_TAG="xhs-ai-ops-mcp:local"
    ;;
esac

export XHS_TARGET_GOARCH="${XHS_TARGET_GOARCH:-${DEFAULT_GOARCH}}"
export XHS_DOCKER_PLATFORM="${XHS_DOCKER_PLATFORM:-${DEFAULT_DOCKER_PLATFORM}}"

# 按需加载 config/.env（保留当前 Shell 已导出的非空环境变量优先）
if [[ -f "${XHS_OPS_ROOT}/config/.env" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"
      val="${val%\"}"
      val="${val#\"}"
      val="${val%\'}"
      val="${val#\'}"
      if [[ -z "${!key:-}" && -n "$val" ]]; then
        export "$key=$val"
      fi
    fi
  done < "${XHS_OPS_ROOT}/config/.env"
fi

export XHS_RUNTIME_DIR="${XHS_OPS_ROOT}/.runtime"
export XHS_MCP_DATA_DIR="${XHS_RUNTIME_DIR}/mcp-data"
export XHS_MCP_COMPOSE_FILE="${XHS_OPS_ROOT}/infra/docker-compose.yml"
export XHS_MCP_CONTAINER_NAME="xhs-ai-ops-mcp"

export XHS_MCP_ADDR="${XHS_MCP_ADDR:-127.0.0.1:18060}"
export XHS_MCP_IMAGE="${XHS_MCP_IMAGE:-${DEFAULT_IMAGE_TAG}}"
export COOKIES_HOST_PATH="${XHS_MCP_DATA_DIR}/cookies.json"

export AGENT_REACH_BIN="${XHS_OPS_ROOT}/.venv/bin/agent-reach"
export BAOYU_IMAGE_GEN_DIR="${XHS_OPS_ROOT}/upstream/baoyu-skills/skills/baoyu-image-gen"
export BAOYU_IMAGE_GEN_MAIN="${BAOYU_IMAGE_GEN_DIR}/scripts/main.ts"
export BAOYU_IMAGE_GEN_BATCH="${BAOYU_IMAGE_GEN_DIR}/scripts/build-batch.ts"

mkdir -p "${XHS_RUNTIME_DIR}" "${XHS_MCP_DATA_DIR}/home" "${XHS_MCP_DATA_DIR}/config"
