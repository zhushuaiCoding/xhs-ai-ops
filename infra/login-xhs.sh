#!/usr/bin/env bash
# 小红书主号扫码登录封装（Docker 容器无界面二维码登录，宿主机不弹第三方浏览器）
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

BASE_URL="http://${XHS_MCP_ADDR}"
QR_PNG="${XHS_RUNTIME_DIR}/xhs-login-qrcode.png"

# 构建可选鉴权头
AUTH_ARGS=()
if [[ -n "${AUTH_TOKEN:-}" ]]; then
  AUTH_ARGS=(-H "Authorization: Bearer ${AUTH_TOKEN}")
fi

if ! curl -sS --noproxy '*' --max-time 3 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "⚠️  xiaohongshu-mcp 容器未运行，正在尝试启动..."
  "${XHS_OPS_ROOT}/infra/start-mcp.sh" start
fi

echo "============================================================"
echo "🔐 小红书主号扫码登录（Docker 隔离模式 · 单主号稳妥模式）"
echo "============================================================"

# 1. 检查是否已登录
STATUS_JSON="$(curl -sS --noproxy '*' --max-time 20 "${AUTH_ARGS[@]}" "${BASE_URL}/api/v1/login/status")"
if python3 -c '
import json, sys
d = json.loads(sys.argv[1])
logged = d.get("data", {}).get("is_logged_in", False)
sys.exit(0 if logged else 1)
' "${STATUS_JSON}" 2>/dev/null; then
  echo "✅ 当前主号已处于登录状态，无需重复扫码！"
  echo "会话文件：${COOKIES_HOST_PATH}"
  exit 0
fi

# 2. 获取登录二维码并保存为本地 PNG
echo "📱 正在从 Docker 容器请求小红书登录二维码..."
QR_JSON="$(curl -sS --noproxy '*' --max-time 60 "${AUTH_ARGS[@]}" "${BASE_URL}/api/v1/login/qrcode")"

python3 - "${QR_JSON}" "${QR_PNG}" <<'PY'
import base64, json, sys

raw, out_path = sys.argv[1], sys.argv[2]
d = json.loads(raw)
if not d.get("success", False):
    print("❌ 获取二维码失败：", d.get("error") or d.get("message") or raw)
    sys.exit(1)

data = d.get("data", {})
if data.get("is_logged_in"):
    print("✅ 检测到已登录。")
    sys.exit(2)

img = data.get("img", "")
if "," in img:
    img = img.split(",", 1)[1]
if not img:
    print("❌ 返回数据中未包含二维码图片：", raw[:300])
    sys.exit(1)

with open(out_path, "wb") as f:
    f.write(base64.b64decode(img))

print(f"✅ 二维码已保存：{out_path}")
if data.get("timeout"):
    print(f"⏱️  二维码有效期：{data.get('timeout')}")
PY
RC=$?
if [[ "$RC" -eq 2 ]]; then
  exit 0
fi

# 自动用 macOS 系统“预览”打开纯 PNG 图片（非第三方浏览器）
if command -v open >/dev/null 2>&1; then
  open "${QR_PNG}"
fi

echo ""
echo "👉 请使用手机小红书 App 扫描弹出的二维码图片：${QR_PNG}"
echo "⚠️  安全提醒：扫码成功后，请勿在其他电脑网页端登录同一主号（会触发互踢）；平时查看主页请直接用手机 App。"
echo "⏳ 正在等待扫码确认（最多等待 120 秒）..."

for _ in $(seq 1 40); do
  sleep 3
  CHECK="$(curl -sS --noproxy '*' --max-time 15 "${AUTH_ARGS[@]}" "${BASE_URL}/api/v1/login/status" 2>/dev/null || true)"
  if python3 -c '
import json, sys
d = json.loads(sys.argv[1])
sys.exit(0 if d.get("data", {}).get("is_logged_in", False) else 1)
' "${CHECK}" 2>/dev/null; then
    rm -f "${QR_PNG}"
    echo ""
    echo "🎉 小红书主号登录成功！会话已加密持久化至：${COOKIES_HOST_PATH}"
    exit 0
  fi
done

echo ""
echo "⚠️  等待超时，如已扫码可稍后执行 ./infra/doctor.sh 复核状态；若二维码过期请重新运行本脚本。"
exit 1
