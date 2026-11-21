#!/usr/bin/env bash
# 小红书 MCP 服务 Docker 容器托管脚本：start | stop | restart | status | logs | pull
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

ACTION="${1:-status}"
HEALTH_URL="http://${XHS_MCP_ADDR}/health"
MCP_URL="http://${XHS_MCP_ADDR}/mcp"

ensure_docker_running() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "❌ 未检测到 docker 命令，请先安装 Docker Desktop 或 OrbStack。"
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker 守护进程未启动！请先打开 Docker Desktop（或 OrbStack / Colima），等图标就绪后再重试。"
    exit 1
  fi
}

compose_cmd() {
  docker compose -f "${XHS_MCP_COMPOSE_FILE}" "$@"
}

start_server() {
  ensure_docker_running

  if ! docker image inspect "${XHS_MCP_IMAGE}" >/dev/null 2>&1; then
    echo "ℹ️  首次使用未找到本地原生镜像 ${XHS_MCP_IMAGE}，正在自动构建（使用 Debian 官方开源 Chromium）..."
    "${XHS_OPS_ROOT}/infra/build-arm64-image.sh"
  fi

  echo "🐳 正在通过 Docker 启动 xiaohongshu-mcp 原生 ARM64 容器（镜像：${XHS_MCP_IMAGE}）..."
  echo "🔒 安全沙箱：仅绑定 ${XHS_MCP_ADDR}，使用官方开源 Chromium，工单目录只读挂载。"
  compose_cmd up -d --force-recreate

  echo "⏳ 等待容器内 MCP 服务健康检查通过..."
  for _ in $(seq 1 40); do
    if curl -sS --noproxy '*' --max-time 2 "${HEALTH_URL}" >/dev/null 2>&1; then
      echo "✅ xiaohongshu-mcp Docker 容器启动成功！"
      echo "   - 容器名: ${XHS_MCP_CONTAINER_NAME}"
      echo "   - MCP 端点: ${MCP_URL}"
      echo "   - 会话持久化目录: ${XHS_MCP_DATA_DIR}"
      return 0
    fi
    sleep 0.5
  done

  echo "⚠️  容器已启动但健康检查暂未就绪，请查看日志："
  compose_cmd logs --tail=30
}

stop_server() {
  ensure_docker_running
  echo "🛑 正在停止并移除 xiaohongshu-mcp 容器（保留 .runtime/mcp-data 会话数据）..."
  compose_cmd down
  echo "✅ 容器已停止。"
}

show_status() {
  if ! docker info >/dev/null 2>&1; then
    echo "⚠️  Docker 守护进程未启动"
    return 0
  fi

  if docker ps --filter "name=^/${XHS_MCP_CONTAINER_NAME}$" --filter "status=running" --format '{{.Names}}' | grep -q "^${XHS_MCP_CONTAINER_NAME}$"; then
    if curl -sS --noproxy '*' --max-time 2 "${HEALTH_URL}" >/dev/null 2>&1; then
      echo "✅ Docker 容器运行中（${XHS_MCP_CONTAINER_NAME}，健康检查通过：${HEALTH_URL}）"
    else
      echo "⚠️  Docker 容器运行中（${XHS_MCP_CONTAINER_NAME}），但健康检查暂未响应：${HEALTH_URL}"
    fi
  else
    echo "⚪ Docker 容器未运行"
  fi
}

case "${ACTION}" in
  start)   start_server ;;
  stop)    stop_server ;;
  restart) ensure_docker_running; compose_cmd restart; sleep 2; show_status ;;
  status)  show_status ;;
  logs)    ensure_docker_running; compose_cmd logs --tail=60 ;;
  pull)    ensure_docker_running; compose_cmd pull ;;
  *)
    echo "用法：$0 {start|stop|restart|status|logs|pull}"
    exit 1
    ;;
esac
