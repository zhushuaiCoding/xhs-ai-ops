#!/usr/bin/env bash
# 本地构建原生架构（arm64 / amd64）Docker 沙箱镜像（Debian 官方开源 Chromium + xiaohongshu-mcp）
# 绝不修改 upstream/ 上游仓库，也不在宿主机遗留二进制文件
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

IMAGE_TAG="${XHS_MCP_IMAGE}"
TARGET_GOARCH="${XHS_TARGET_GOARCH}"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/xhs-docker-build.XXXXXX")"
trap 'rm -rf "${TMP_DIR}"' EXIT

if [[ ! -d "${XHS_OPS_ROOT}/upstream/xiaohongshu-mcp" ]]; then
  echo "❌ 未找到上游仓库 upstream/xiaohongshu-mcp，请先运行 ./infra/bootstrap.sh"
  exit 1
fi

echo "🔧 [1/3] 准备临时构建上下文（不改动 upstream 源码，目标架构：linux/${TARGET_GOARCH}）..."
cp -R "${XHS_OPS_ROOT}/upstream/xiaohongshu-mcp" "${TMP_DIR}/src"

python3 - "${TMP_DIR}/src" <<'PY'
from pathlib import Path
import sys

src = Path(sys.argv[1])

# 1) 让 EnsureBrowser 优先使用容器内 Debian 官方开源 Chromium（XHS_BROWSER_BIN）
dl = src / "browser/browser_download.go"
s = dl.read_text(encoding="utf-8")
old = "func EnsureBrowser() (string, error) {"
new = """func EnsureBrowser() (string, error) {
\tif envBin := strings.TrimSpace(os.Getenv("XHS_BROWSER_BIN")); envBin != "" {
\t\tif _, err := os.Stat(envBin); err == nil {
\t\t\treturn envBin, nil
\t\t}
\t}"""
assert old in s, "EnsureBrowser anchor not found"
dl.write_text(s.replace(old, new, 1), encoding="utf-8")

# 2) 官方开源 Chromium 适配：
#    - 关闭仅适用于 CloakBrowser 的 WithFingerprint（避免 buildUAOverride 注入 HeadlessChrome UA）
#    - 启用 go-rod/stealth 补丁 + 标准桌面 Chrome UA + disable-blink-features=AutomationControlled
br = src / "browser/browser.go"
b = br.read_text(encoding="utf-8")
old_opts = """\topts := []headless_browser.Option{
\t\theadless_browser.WithHeadless(headless),
\t\t// 用内置浏览器的默认配置，不强制 UA。
\t\theadless_browser.WithFingerprint(""), // 空 = 按运行 OS 自动：Linux→windows，mac→macos
\t\theadless_browser.WithStealthJS(false),
\t\theadless_browser.WithLanguage("zh-CN"), // 面向小红书
\t\t// 品牌报 Chrome。
\t\t// 注：hardware-concurrency 不设，交给 seed 派生。
\t\theadless_browser.WithExtraFlags(map[string]string{"fingerprint-brand": "Chrome"}),
\t}"""
new_opts = """\topts := []headless_browser.Option{
\t\theadless_browser.WithHeadless(headless),
\t\theadless_browser.WithUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"),
\t\theadless_browser.WithStealthJS(true),
\t\theadless_browser.WithExtraFlags(map[string]string{
\t\t\t"disable-blink-features": "AutomationControlled",
\t\t\t"lang":                   "zh-CN",
\t\t\t"window-size":            "1440,900",
\t\t}),
\t}"""
assert old_opts in b, "browser.go opts block not found"
b = b.replace(old_opts, new_opts, 1)
b = b.replace(
    '\tif cfg.fingerprintSeed > 0 {\n\t\topts = append(opts, headless_browser.WithFingerprintSeed(cfg.fingerprintSeed))\n\t\tlogrus.Infof("fingerprint seed pinned: %d", cfg.fingerprintSeed)\n\t}',
    '\t_ = cfg.fingerprintSeed',
    1,
)
br.write_text(b, encoding="utf-8")

# 3) 登录检测与二维码加载：对页面重定向宽容等待，避免未登录跳转时直接 panic
lg = src / "xiaohongshu/login.go"
l = lg.read_text(encoding="utf-8")
l = l.replace(
    'pp.MustNavigate("https://www.xiaohongshu.com/explore").MustWaitLoad()',
    'if err := pp.Navigate("https://www.xiaohongshu.com/explore"); err != nil {\n\t\tlogrus.Warnf("navigate warning: %v", err)\n\t}\n\t_ = pp.WaitLoad()\n\t_ = pp.WaitDOMStable(time.Second, 0.1)',
)
if '"github.com/sirupsen/logrus"' not in l:
    l = l.replace('"github.com/pkg/errors"', '"github.com/pkg/errors"\n\t"github.com/sirupsen/logrus"', 1)
lg.write_text(l, encoding="utf-8")

# 4) 创作者中心会话兼容（适配 2026 新版创作者中心）：
#    - 除检测旧版 galaxy_creator_session_id 外，若页面已进入 creator.xiaohongshu.com/new/ 或 /publish/（非 /login），即视为会话就绪
cs = src / "xiaohongshu/creator_session.go"
c = cs.read_text(encoding="utf-8")
c = c.replace("creatorSessionTimeout = 15 * time.Second", "creatorSessionTimeout = 25 * time.Second", 1)
if '"strings"' not in c:
    c = c.replace('"time"', '"strings"\n\t"time"', 1)
old_has = """func hasCreatorSession(page *rod.Page) bool {
\tcks, err := page.Browser().GetCookies()
\tif err != nil {
\t\treturn false
\t}
\tfor _, c := range cks {
\t\tif c.Name == creatorSessionCookie {
\t\t\treturn true
\t\t}
\t}
\treturn false
}"""
new_has = """func hasCreatorSession(page *rod.Page) bool {
\tif info, err := page.Info(); err == nil && info != nil {
\t\tif strings.HasPrefix(info.URL, "https://creator.xiaohongshu.com/") &&
\t\t\t!strings.Contains(info.URL, "/login") &&
\t\t\t(strings.Contains(info.URL, "/new/") || strings.Contains(info.URL, "/publish")) {
\t\t\treturn true
\t\t}
\t}
\tcks, err := page.Browser().GetCookies()
\tif err != nil {
\t\treturn false
\t}
\tfor _, c := range cks {
\t\tif c.Name == creatorSessionCookie || c.Name == "access-token-creator.xiaohongshu.com" {
\t\t\treturn true
\t\t}
\t}
\treturn false
}"""
assert old_has in c, "hasCreatorSession block not found"
c = c.replace(old_has, new_has, 1)
old_ret = '\treturn errors.New("创作者中心登录失效，请重新扫码登录")'
new_ret = """\tinfo, _ := page.Info()
\tcurURL, curTitle := "", ""
\tif info != nil {
\t\tcurURL, curTitle = info.URL, info.Title
\t}
\treturn errors.Errorf("创作者中心登录失效（当前页面: %s | 标题: %s），请确认账号已在创作者中心登录或完成实名认证", curURL, curTitle)"""
if old_ret in c:
    c = c.replace(old_ret, new_ret, 1)
cs.write_text(c, encoding="utf-8")

print("✅ 源码补丁注入完成（仅在临时目录生效）")
PY

echo "⚙️  [2/3] 交叉编译 linux/${TARGET_GOARCH} 原生二进制..."
mkdir -p "${TMP_DIR}/ctx"
(
  cd "${TMP_DIR}/src"
  CGO_ENABLED=0 GOOS=linux GOARCH="${TARGET_GOARCH}" GOPROXY=https://goproxy.cn,direct \
    go build -ldflags="-s -w -X main.version=local-${TARGET_GOARCH}" -o "${TMP_DIR}/ctx/app" .
)

# 智能选择基础镜像：优先复用本地已有同架构 Debian Bookworm 镜像，否则使用 debian:bookworm-slim
BASE_IMAGE="${XHS_BASE_IMAGE:-}"
if [[ -z "${BASE_IMAGE}" ]]; then
  if docker image inspect python:3.12-slim-bookworm >/dev/null 2>&1; then
    BASE_IMAGE="python:3.12-slim-bookworm"
  else
    BASE_IMAGE="debian:bookworm-slim"
  fi
fi

sed "s|^FROM .*|FROM ${BASE_IMAGE}|" "${XHS_OPS_ROOT}/infra/Dockerfile.arm64" > "${TMP_DIR}/ctx/Dockerfile"

echo "🐳 [3/3] 构建原生 linux/${TARGET_GOARCH} 安全沙箱镜像：${IMAGE_TAG}（底座：${BASE_IMAGE}）..."
DOCKER_BUILDKIT=0 docker build -t "${IMAGE_TAG}" "${TMP_DIR}/ctx"
echo "✅ 镜像构建成功：${IMAGE_TAG}"
