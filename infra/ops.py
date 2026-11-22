#!/usr/bin/env python3
"""xhs-ai-ops 跨平台统一运维引擎（支持 Windows 11 / macOS / Linux）。

统一收口：
  bootstrap | build-image | start | stop | restart | status | logs | pull
  login | reach | gen-image | build-batch | install-skills | doctor
"""

from __future__ import annotations

import base64
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

IS_WINDOWS = os.name == "nt"
IS_MACOS = sys.platform == "darwin"

XHS_OPS_ROOT = Path(__file__).resolve().parent.parent
XHS_WORKSPACE_DIR = Path(os.environ.get("XHS_WORKSPACE_DIR") or XHS_OPS_ROOT.parent).resolve()

SKILLS = (
    "xhs-orchestrator",
    "xhs-research-ops",
    "xhs-content-writer",
    "xhs-visual-studio",
    "xhs-publish-engage",
)


def configure_stdio() -> None:
    """确保 Windows GBK 控制台也能正常输出中文与符号。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def detect_arch() -> tuple[str, str, str]:
    """自动探测宿主机 CPU 架构，返回 (goarch, docker_platform, default_image_tag)。"""
    raw = platform.machine().lower()
    if raw in ("arm64", "aarch64"):
        return "arm64", "linux/arm64", "xhs-ai-ops-mcp:arm64"
    if raw in ("x86_64", "amd64", "x64"):
        return "amd64", "linux/amd64", "xhs-ai-ops-mcp:amd64"
    return "amd64", "linux/amd64", "xhs-ai-ops-mcp:local"


def load_dotenv(env_file: Path, env: dict[str, str]) -> None:
    """按需加载 config/.env，已导出的非空系统环境变量优先。"""
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        if not env.get(key) and val:
            env[key] = val


def build_env() -> dict[str, str]:
    """组装完整跨平台运行环境变量并确保运行期目录存在。"""
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["XHS_OPS_ROOT"] = str(XHS_OPS_ROOT)
    env["XHS_WORKSPACE_DIR"] = str(XHS_WORKSPACE_DIR)

    goarch, docker_platform, image_tag = detect_arch()
    load_dotenv(XHS_OPS_ROOT / "config" / ".env", env)

    env.setdefault("XHS_TARGET_GOARCH", goarch)
    env.setdefault("XHS_DOCKER_PLATFORM", docker_platform)
    env.setdefault("XHS_MCP_IMAGE", image_tag)
    env.setdefault("XHS_MCP_ADDR", "127.0.0.1:18060")
    env["XHS_MCP_CONTAINER_NAME"] = "xhs-ai-ops-mcp"

    runtime_dir = XHS_OPS_ROOT / ".runtime"
    mcp_data_dir = runtime_dir / "mcp-data"
    (mcp_data_dir / "home").mkdir(parents=True, exist_ok=True)
    (mcp_data_dir / "config").mkdir(parents=True, exist_ok=True)
    (XHS_OPS_ROOT / "workspace" / "posts").mkdir(parents=True, exist_ok=True)

    env["XHS_RUNTIME_DIR"] = str(runtime_dir)
    env["XHS_MCP_DATA_DIR"] = str(mcp_data_dir)
    env["XHS_MCP_COMPOSE_FILE"] = str(XHS_OPS_ROOT / "infra" / "docker-compose.yml")
    env["COOKIES_HOST_PATH"] = str(mcp_data_dir / "cookies.json")
    return env


def venv_bin(name: str) -> Path:
    """跨平台定位项目 .venv 内可执行文件路径。"""
    if IS_WINDOWS:
        return XHS_OPS_ROOT / ".venv" / "Scripts" / f"{name}.exe"
    return XHS_OPS_ROOT / ".venv" / "bin" / name


def http_get_direct(url: str, timeout: float = 5.0, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    """直连请求本机 MCP 端点（强制绕过系统 HTTP/SOCKS 代理）。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with opener.open(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def is_mcp_healthy(addr: str, timeout: float = 2.0) -> bool:
    try:
        status, _ = http_get_direct(f"http://{addr}/health", timeout=timeout)
        return 200 <= status < 300
    except Exception:
        return False


def ensure_docker_running() -> None:
    if not shutil.which("docker"):
        print("❌ 未检测到 docker 命令，请先安装 Docker Desktop（Windows 11 推荐开启 WSL2 后端）。")
        sys.exit(1)
    rc = subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode
    if rc != 0:
        print("❌ Docker 守护进程未启动！请先打开 Docker Desktop（或 OrbStack / Colima），等图标就绪后再重试。")
        sys.exit(1)


def docker_compose(env: dict[str, str], args: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", "-f", env["XHS_MCP_COMPOSE_FILE"], *args]
    return subprocess.run(
        cmd,
        env=env,
        cwd=str(XHS_OPS_ROOT),
        capture_output=capture,
        text=capture,
    )


def remove_readonly(func, path, _exc_info) -> None:
    """Windows 临时目录清理兜底（去除只读属性后重试删除）。"""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def parse_go_version(ver_text: str) -> tuple[int, int, int] | None:
    m = re.search(r"go(\d+)\.(\d+)(?:\.(\d+))?", ver_text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def read_required_go_version(src_dir: Path) -> str:
    go_mod = src_dir / "go.mod"
    if go_mod.is_file():
        m = re.search(r"^go\s+(\d+\.\d+(?:\.\d+)?)", go_mod.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    return "1.27.3"


def can_build_go_on_host(required_ver: str) -> bool:
    go_bin = shutil.which("go")
    if not go_bin:
        return False
    res = subprocess.run([go_bin, "version"], capture_output=True, text=True)
    if res.returncode != 0:
        return False
    host_v = parse_go_version(res.stdout)
    req_v = parse_go_version(f"go{required_ver}")
    if not host_v or not req_v:
        return False
    return host_v >= req_v


def apply_mcp_patches(src: Path) -> None:
    """对临时目录中的 xiaohongshu-mcp 源码注入 5 项安全与跨平台补丁（绝不改动 upstream/）。"""
    # 1) 让 EnsureBrowser 优先使用容器内 Debian 官方开源 Chromium（XHS_BROWSER_BIN）
    dl = src / "browser" / "browser_download.go"
    s = dl.read_text(encoding="utf-8")
    old = "func EnsureBrowser() (string, error) {"
    new = """func EnsureBrowser() (string, error) {
\tif envBin := strings.TrimSpace(os.Getenv("XHS_BROWSER_BIN")); envBin != "" {
\t\tif _, err := os.Stat(envBin); err == nil {
\t\t\treturn envBin, nil
\t\t}
\t}"""
    if old not in s:
        raise RuntimeError("EnsureBrowser anchor not found in browser/browser_download.go")
    dl.write_text(s.replace(old, new, 1), encoding="utf-8")

    # 2) 官方开源 Chromium 适配（关闭 CloakBrowser 专属参数 + stealth + 标准桌面 UA）
    br = src / "browser" / "browser.go"
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
\t\theadless_browser.WithUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"),
\t\theadless_browser.WithStealthJS(true),
\t\theadless_browser.WithExtraFlags(map[string]string{
\t\t\t"disable-blink-features": "AutomationControlled",
\t\t\t"lang":                   "zh-CN",
\t\t\t"window-size":            "1440,900",
\t\t}),
\t}"""
    if old_opts not in b:
        raise RuntimeError("browser.go opts block not found")
    b = b.replace(old_opts, new_opts, 1)
    b = b.replace(
        '\tif cfg.fingerprintSeed > 0 {\n\t\topts = append(opts, headless_browser.WithFingerprintSeed(cfg.fingerprintSeed))\n\t\tlogrus.Infof("fingerprint seed pinned: %d", cfg.fingerprintSeed)\n\t}',
        "\t_ = cfg.fingerprintSeed",
        1,
    )
    br.write_text(b, encoding="utf-8")

    # 3) 登录检测与二维码加载：对页面重定向宽容等待，避免未登录跳转时 panic
    lg = src / "xiaohongshu" / "login.go"
    l = lg.read_text(encoding="utf-8")
    l = l.replace(
        'pp.MustNavigate("https://www.xiaohongshu.com/explore").MustWaitLoad()',
        'if err := pp.Navigate("https://www.xiaohongshu.com/explore"); err != nil {\n\t\tlogrus.Warnf("navigate warning: %v", err)\n\t}\n\t_ = pp.WaitLoad()\n\t_ = pp.WaitDOMStable(time.Second, 0.1)',
    )
    if '"github.com/sirupsen/logrus"' not in l:
        l = l.replace('"github.com/pkg/errors"', '"github.com/pkg/errors"\n\t"github.com/sirupsen/logrus"', 1)
    lg.write_text(l, encoding="utf-8")

    # 4) 创作者中心会话兼容（适配 2026 新版创作者中心）
    cs = src / "xiaohongshu" / "creator_session.go"
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
    if old_has not in c:
        raise RuntimeError("hasCreatorSession block not found")
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

    # 5) 跨平台工单路径归一化：Windows/macOS 宿主机 workspace/posts/... 绝对路径自动映射至容器只读卷 /app/posts/...
    proc = src / "pkg" / "downloader" / "processor.go"
    p = proc.read_text(encoding="utf-8")
    p = p.replace(
        'import (\n\t"fmt"',
        'import (\n\t"fmt"\n\t"os"\n\t"path/filepath"\n\t"strings"',
        1,
    )
    old_append = "\t\t\tlocalPaths = append(localPaths, image)"
    new_append = "\t\t\tlocalPaths = append(localPaths, ResolveContainerMediaPath(image))"
    if old_append not in p:
        raise RuntimeError("processor.go localPaths append anchor not found")
    p = p.replace(old_append, new_append, 1)
    p += """

// ResolveContainerMediaPath 将 Windows/macOS/Linux 宿主机上的 workspace/posts/... 路径自动映射至容器内只读挂载点 /app/posts/...
func ResolveContainerMediaPath(raw string) string {
\traw = strings.TrimSpace(raw)
\tif raw == "" {
\t\treturn raw
\t}
\tif _, err := os.Stat(raw); err == nil {
\t\treturn raw
\t}
\tnorm := strings.ReplaceAll(raw, "\\\\", "/")
\tlower := strings.ToLower(norm)
\tfor _, marker := range []string{"/workspace/posts/", "workspace/posts/"} {
\t\tif idx := strings.Index(lower, marker); idx >= 0 {
\t\t\trel := strings.TrimPrefix(norm[idx+len(marker):], "/")
\t\t\tcleanRel := filepath.Clean(filepath.FromSlash(rel))
\t\t\tif cleanRel == "." || strings.HasPrefix(cleanRel, "..") || filepath.IsAbs(cleanRel) {
\t\t\t\tcontinue
\t\t\t}
\t\t\tcand := filepath.Join("/app/posts", cleanRel)
\t\t\tif _, err := os.Stat(cand); err == nil {
\t\t\t\treturn cand
\t\t\t}
\t\t}
\t}
\treturn raw
}
"""
    proc.write_text(p, encoding="utf-8")

    svc = src / "service.go"
    sv = svc.read_text(encoding="utf-8")
    old_vid = '\tif _, err := os.Stat(req.Video); err != nil {'
    new_vid = '\treq.Video = downloader.ResolveContainerMediaPath(req.Video)\n\tif _, err := os.Stat(req.Video); err != nil {'
    if old_vid in sv:
        sv = sv.replace(old_vid, new_vid, 1)
        svc.write_text(sv, encoding="utf-8")


# ---------------------------------------------------------------------------
# 子命令实现
# ---------------------------------------------------------------------------

def cmd_bootstrap(env: dict[str, str], _args: list[str]) -> int:
    upstream_dir = XHS_OPS_ROOT / "upstream"
    for sub in (
        upstream_dir,
        XHS_OPS_ROOT / "knowledge-base" / "accounts",
        XHS_OPS_ROOT / "knowledge-base" / "topics",
        XHS_OPS_ROOT / "knowledge-base" / "patterns",
        XHS_OPS_ROOT / "knowledge-base" / "actions",
        XHS_OPS_ROOT / "knowledge-base" / "reviews",
        XHS_OPS_ROOT / "workspace" / "posts",
    ):
        sub.mkdir(parents=True, exist_ok=True)

    print("============================================================")
    print("🚀 xhs-ai-ops 一键初始化（跨平台 · 拉取 5 个上游开源底座）")
    print(f"项目目录：{XHS_OPS_ROOT}")
    print("============================================================")

    if not shutil.which("git"):
        print("❌ 未检测到 git，请先安装 Git 后重试。")
        return 1

    repos = [
        ("Agent-Reach", "https://github.com/Panniantong/Agent-Reach.git"),
        ("xiaohongshu-ops-skill", "https://github.com/Xiangyu-CAS/xiaohongshu-ops-skill.git"),
        ("xhs-visual-director-skill", "https://github.com/ziguishian/xhs-visual-director-skill.git"),
        ("baoyu-skills", "https://github.com/JimLiu/baoyu-skills.git"),
    ]
    for name, url in repos:
        dst = upstream_dir / name
        if (dst / ".git").exists():
            print(f"✅ 已存在上游仓库：{name}（如需更新请手动在该目录执行 git pull）")
        else:
            print(f"⬇️  正在拉取 {name} ({url}) ...")
            subprocess.run(["git", "clone", "--depth", "1", url, str(dst)], check=True)

    mcp_dst = upstream_dir / "xiaohongshu-mcp"
    if (mcp_dst / ".git").exists():
        print("✅ 已存在上游仓库：xiaohongshu-mcp")
    else:
        print("⬇️  正在拉取 xiaohongshu-mcp（跳过演示大动图加速检出源码）...")
        subprocess.run(
            [
                "git",
                "-c",
                "http.version=HTTP/1.1",
                "-c",
                "http.postBuffer=524288000",
                "clone",
                "--depth",
                "1",
                "--filter=blob:limit=2m",
                "--no-checkout",
                "https://github.com/xpzouying/xiaohongshu-mcp.git",
                str(mcp_dst),
            ],
            check=True,
        )
        subprocess.run(["git", "sparse-checkout", "init", "--no-cone"], cwd=str(mcp_dst), check=True)
        (mcp_dst / ".git" / "info" / "sparse-checkout").write_bytes(b"/*\n!/assets/\n")
        subprocess.run(["git", "checkout"], cwd=str(mcp_dst), check=True)

    print("\n🐍 正在初始化项目独立 Python 虚拟环境并安装 Agent-Reach...")
    venv_py = venv_bin("python")
    venv_pip = venv_bin("pip")
    if not venv_py.is_file():
        subprocess.run([sys.executable, "-m", "venv", str(XHS_OPS_ROOT / ".venv")], check=True)
    subprocess.run([str(venv_py), "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)
    subprocess.run([str(venv_pip), "install", "-q", "-e", str(upstream_dir / "Agent-Reach")], check=True)
    print(f"✅ Agent-Reach 安装完成：{venv_bin('agent-reach')}")

    env_file = XHS_OPS_ROOT / "config" / ".env"
    env_example = XHS_OPS_ROOT / "config" / ".env.example"
    if not env_file.is_file() and env_example.is_file():
        shutil.copy2(env_example, env_file)
        print("📝 已生成本地配置模板：config/.env（请按需填入 API Key）")

    py_cmd = "python" if IS_WINDOWS else "python3"
    print("\n============================================================")
    print("🎉 初始化完成！接下来执行以下 4 步即可开始使用：")
    print(f"   1. 打开 Docker Desktop，运行：{py_cmd} infra/ops.py start")
    print(f"   2. 扫码登录小红书主号：{py_cmd} infra/ops.py login")
    print(f"   3. 注册 Skills 与 MCP 到 AI 客户端：{py_cmd} infra/ops.py install-skills")
    print(f"   4. 一键环境体检：{py_cmd} infra/ops.py doctor")
    print("============================================================")
    return 0


def pick_base_image(env: dict[str, str]) -> str:
    if env.get("XHS_BASE_IMAGE"):
        return env["XHS_BASE_IMAGE"]
    res = subprocess.run(
        ["docker", "image", "inspect", "python:3.12-slim-bookworm", "--format", "{{.Architecture}}"],
        capture_output=True,
        text=True,
    )
    if res.returncode == 0 and res.stdout.strip() == env["XHS_TARGET_GOARCH"]:
        return "python:3.12-slim-bookworm"
    return "debian:bookworm-slim"


def cmd_build_image(env: dict[str, str], args: list[str]) -> int:
    force_docker_go = "--docker-build" in args
    upstream_mcp = XHS_OPS_ROOT / "upstream" / "xiaohongshu-mcp"
    if not upstream_mcp.is_dir():
        print("❌ 未找到上游仓库 upstream/xiaohongshu-mcp，请先运行：python infra/ops.py bootstrap")
        return 1

    ensure_docker_running()
    image_tag = env["XHS_MCP_IMAGE"]
    target_goarch = env["XHS_TARGET_GOARCH"]
    target_platform = env["XHS_DOCKER_PLATFORM"]

    tmp_dir = Path(tempfile.mkdtemp(prefix="xhs-docker-build-"))
    try:
        src_dir = tmp_dir / "src"
        ctx_dir = tmp_dir / "ctx"
        ctx_dir.mkdir(parents=True, exist_ok=True)

        print(f"🔧 [1/3] 准备临时构建上下文（不改动 upstream 源码，目标架构：{target_platform}）...")
        shutil.copytree(
            upstream_mcp,
            src_dir,
            ignore=shutil.ignore_patterns(".git", "assets"),
        )
        apply_mcp_patches(src_dir)
        print("✅ 5 项源码补丁注入完成（含 Debian 官方 Chromium + 2026 创作者中心 + Windows/macOS 工单路径自适应）")

        req_go_ver = read_required_go_version(src_dir)
        base_image = pick_base_image(env)
        runtime_template = (XHS_OPS_ROOT / "infra" / "Dockerfile.arm64").read_text(encoding="utf-8")
        runtime_stage = re.sub(r"^FROM .*", f"FROM {base_image}", runtime_template, count=1, flags=re.M)

        use_host_go = (not force_docker_go) and can_build_go_on_host(req_go_ver)
        if use_host_go:
            print(f"⚙️  [2/3] 使用宿主机 Go 交叉编译 {target_platform} 原生二进制...")
            go_env = dict(env)
            go_env["CGO_ENABLED"] = "0"
            go_env["GOOS"] = "linux"
            go_env["GOARCH"] = target_goarch
            go_env.setdefault("GOPROXY", "https://goproxy.cn,direct")
            subprocess.run(
                [
                    "go",
                    "build",
                    f"-ldflags=-s -w -X main.version=local-{target_goarch}",
                    "-o",
                    str(ctx_dir / "app"),
                    ".",
                ],
                cwd=str(src_dir),
                env=go_env,
                check=True,
            )
            (ctx_dir / "Dockerfile").write_text(runtime_stage, encoding="utf-8")
        else:
            print(f"⚙️  [2/3] 宿主机未安装 Go {req_go_ver}+，自动切换为 Docker 容器多阶段编译（免宿主机安装 Go）...")
            shutil.move(str(src_dir), str(ctx_dir / "src"))
            builder_stage = f"""FROM golang:{req_go_ver} AS builder
WORKDIR /src
ENV GOPROXY=https://goproxy.cn,direct
ENV GOSUMDB=sum.golang.google.cn
COPY src/go.mod src/go.sum ./
RUN go mod download
COPY src/ .
RUN CGO_ENABLED=0 GOOS=linux GOARCH={target_goarch} go build -ldflags="-s -w -X main.version=local-{target_goarch}" -o /out/app .

"""
            runtime_multi = runtime_stage.replace("COPY app /app/app", "COPY --from=builder /out/app /app/app", 1)
            (ctx_dir / "Dockerfile").write_text(builder_stage + runtime_multi, encoding="utf-8")

        print(f"🐳 [3/3] 构建原生 {target_platform} 安全沙箱镜像：{image_tag}（底座：{base_image}）...")
        build_env_map = dict(env)
        build_env_map.setdefault("DOCKER_BUILDKIT", "1" if not use_host_go else "0")
        subprocess.run(
            ["docker", "build", "--platform", target_platform, "-t", image_tag, str(ctx_dir)],
            env=build_env_map,
            check=True,
        )
        print(f"✅ 镜像构建成功：{image_tag}")
        return 0
    finally:
        shutil.rmtree(tmp_dir, onerror=remove_readonly)


def cmd_start(env: dict[str, str], _args: list[str]) -> int:
    ensure_docker_running()
    image = env["XHS_MCP_IMAGE"]
    if subprocess.run(["docker", "image", "inspect", image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        print(f"ℹ️  首次使用未找到本地原生镜像 {image}，正在自动构建（Debian 官方开源 Chromium）...")
        rc = cmd_build_image(env, [])
        if rc != 0:
            return rc

    print(f"🐳 正在通过 Docker 启动 xiaohongshu-mcp 原生 {env['XHS_DOCKER_PLATFORM']} 容器（镜像：{image}）...")
    print(f"🔒 安全沙箱：仅绑定 {env['XHS_MCP_ADDR']}，使用官方开源 Chromium，工单目录只读挂载（/app/posts:ro）。")
    res = docker_compose(env, ["up", "-d", "--force-recreate"])
    if res.returncode != 0:
        return res.returncode

    print("⏳ 等待容器内 MCP 服务健康检查通过...")
    for _ in range(40):
        if is_mcp_healthy(env["XHS_MCP_ADDR"]):
            print("✅ xiaohongshu-mcp Docker 容器启动成功！")
            print(f"   - 容器名: {env['XHS_MCP_CONTAINER_NAME']}")
            print(f"   - MCP 端点: http://{env['XHS_MCP_ADDR']}/mcp")
            print(f"   - 会话持久化目录: {env['XHS_MCP_DATA_DIR']}")
            return 0
        time.sleep(0.5)

    print("⚠️  容器已启动但健康检查暂未就绪，请查看日志：")
    docker_compose(env, ["logs", "--tail=30"])
    return 1


def cmd_stop(env: dict[str, str], _args: list[str]) -> int:
    ensure_docker_running()
    print("🛑 正在停止并移除 xiaohongshu-mcp 容器（保留 .runtime/mcp-data 会话数据）...")
    res = docker_compose(env, ["down"])
    if res.returncode == 0:
        print("✅ 容器已停止。")
    return res.returncode


def cmd_status(env: dict[str, str], _args: list[str]) -> int:
    if subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        print("⚠️  Docker 守护进程未启动")
        return 0
    cname = env["XHS_MCP_CONTAINER_NAME"]
    res = subprocess.run(
        ["docker", "ps", "--filter", f"name=^/{cname}$", "--filter", "status=running", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    if cname in res.stdout.splitlines():
        health_url = f"http://{env['XHS_MCP_ADDR']}/health"
        if is_mcp_healthy(env["XHS_MCP_ADDR"]):
            print(f"✅ Docker 容器运行中（{cname}，健康检查通过：{health_url}）")
        else:
            print(f"⚠️  Docker 容器运行中（{cname}），但健康检查暂未响应：{health_url}")
    else:
        print("⚪ Docker 容器未运行")
    return 0


def cmd_restart(env: dict[str, str], _args: list[str]) -> int:
    ensure_docker_running()
    res = docker_compose(env, ["restart"])
    if res.returncode != 0:
        return res.returncode
    time.sleep(2)
    return cmd_status(env, [])


def cmd_logs(env: dict[str, str], _args: list[str]) -> int:
    ensure_docker_running()
    return docker_compose(env, ["logs", "--tail=60"]).returncode


def cmd_pull(env: dict[str, str], _args: list[str]) -> int:
    ensure_docker_running()
    return docker_compose(env, ["pull"]).returncode


def open_image_viewer(path: Path) -> None:
    """用系统默认图片查看器打开纯 PNG（绝不弹第三方浏览器）。"""
    try:
        if IS_WINDOWS:
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif IS_MACOS and shutil.which("open"):
            subprocess.Popen(["open", str(path)])
        elif shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def cmd_login(env: dict[str, str], _args: list[str]) -> int:
    addr = env["XHS_MCP_ADDR"]
    base_url = f"http://{addr}"
    qr_png = Path(env["XHS_RUNTIME_DIR"]) / "xhs-login-qrcode.png"
    headers = {"Authorization": f"Bearer {env['AUTH_TOKEN']}"} if env.get("AUTH_TOKEN") else {}

    if not is_mcp_healthy(addr, timeout=3.0):
        print("⚠️  xiaohongshu-mcp 容器未运行，正在尝试启动...")
        if cmd_start(env, []) != 0:
            return 1

    print("============================================================")
    print("🔐 小红书主号扫码登录（Docker 隔离模式 · 单主号稳妥模式）")
    print("============================================================")

    try:
        _, raw = http_get_direct(f"{base_url}/api/v1/login/status", timeout=20.0, headers=headers)
        if json.loads(raw.decode("utf-8")).get("data", {}).get("is_logged_in"):
            print("✅ 当前主号已处于登录状态，无需重复扫码！")
            print(f"会话文件：{env['COOKIES_HOST_PATH']}")
            return 0
    except Exception:
        pass

    print("📱 正在从 Docker 容器请求小红书登录二维码...")
    try:
        _, raw_qr = http_get_direct(f"{base_url}/api/v1/login/qrcode", timeout=60.0, headers=headers)
        data_root = json.loads(raw_qr.decode("utf-8"))
    except Exception as exc:
        print(f"❌ 请求登录二维码失败：{exc}")
        return 1

    if not data_root.get("success"):
        print("❌ 获取二维码失败：", data_root.get("error") or data_root.get("message") or data_root)
        return 1

    payload = data_root.get("data", {})
    if payload.get("is_logged_in"):
        print("✅ 检测到已登录。")
        return 0

    img = payload.get("img", "")
    if "," in img:
        img = img.split(",", 1)[1]
    if not img:
        print("❌ 返回数据中未包含二维码图片。")
        return 1

    qr_png.write_bytes(base64.b64decode(img))
    print(f"✅ 二维码已保存：{qr_png}")
    if payload.get("timeout"):
        print(f"⏱️  二维码有效期：{payload.get('timeout')}")

    open_image_viewer(qr_png)

    print("")
    print(f"👉 请使用手机小红书 App 扫描弹出的二维码图片：{qr_png}")
    print("⚠️  安全提醒：扫码成功后，请勿在其他电脑网页端登录同一主号（会触发互踢）；日常查看主页请直接用手机 App。")
    print("⏳ 正在等待扫码确认（最多等待 120 秒）...")

    for _ in range(40):
        time.sleep(3)
        try:
            _, chk = http_get_direct(f"{base_url}/api/v1/login/status", timeout=15.0, headers=headers)
            if json.loads(chk.decode("utf-8")).get("data", {}).get("is_logged_in"):
                qr_png.unlink(missing_ok=True)
                print(f"\n🎉 小红书主号登录成功！会话已持久化至：{env['COOKIES_HOST_PATH']}")
                return 0
        except Exception:
            pass

    print("\n⚠️  等待超时，如已扫码可稍后执行 doctor 复核状态；若二维码过期请重新运行本命令。")
    return 1


def cmd_reach(env: dict[str, str], args: list[str]) -> int:
    reach_bin = venv_bin("agent-reach")
    if not reach_bin.is_file():
        print(f"❌ 未找到 Agent-Reach 可执行文件：{reach_bin}（请先运行 python infra/ops.py bootstrap）")
        return 1

    if env.get("ALLOW_REACH_XHS", "0") != "1":
        for arg in args:
            low = arg.lower()
            if low == "xiaohongshu" or "xiaohongshu.com" in low or "xhslink.com" in low:
                print("⛔ [风控保护] 当前为单主号稳妥模式，已拦截 Agent-Reach 访问小红书渠道。")
                print("👉 小红书站内检索、详情与推荐流请统一使用 xiaohongshu-mcp（search_feeds / list_feeds / get_feed_detail）。")
                print("👉 若已配置独立采集小号，请显式传入 ALLOW_REACH_XHS=1 后重试。")
                return 2

    # 自动注入 certifi 根证书包，防止 macOS/Windows Python 缺失系统 CA
    venv_py = venv_bin("python")
    if not env.get("SSL_CERT_FILE") and venv_py.is_file():
        res = subprocess.run([str(venv_py), "-c", "import certifi; print(certifi.where())"], capture_output=True, text=True)
        cert_path = res.stdout.strip()
        if res.returncode == 0 and cert_path and Path(cert_path).is_file():
            env["SSL_CERT_FILE"] = cert_path
            env["REQUESTS_CA_BUNDLE"] = cert_path

    return subprocess.run([str(reach_bin), *args], env=env).returncode


def resolve_bun_runner() -> list[str] | None:
    bun = shutil.which("bun")
    if bun:
        return [bun]
    npx = shutil.which("npx")
    if npx:
        return [npx, "-y", "bun"]
    return None


def run_baoyu_script(env: dict[str, str], script_name: str, args: list[str]) -> int:
    script = XHS_OPS_ROOT / "upstream" / "baoyu-skills" / "skills" / "baoyu-image-gen" / "scripts" / script_name
    if not script.is_file():
        print(f"❌ 未找到 baoyu-image-gen 脚本：{script}（请先运行 python infra/ops.py bootstrap）")
        return 1
    runner = resolve_bun_runner()
    if not runner:
        print("❌ 未检测到 bun 或 npx（Node.js 18+），请先安装 bun 或 Node.js。")
        return 1
    return subprocess.run([*runner, str(script), *args], cwd=str(XHS_OPS_ROOT), env=env).returncode


def is_reparse_point(path: Path) -> bool:
    """安全判断路径是否为符号链接或 Windows 目录联接（Junction）。"""
    if path.is_symlink():
        return True
    if IS_WINDOWS and path.exists():
        try:
            st = os.lstat(path)
            return bool(getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except Exception:
            return False
    return False


def safe_remove_target(dst: Path) -> None:
    """删除旧的技能挂载目录，严禁跟随符号链接或 Junction 删除源目录。"""
    if is_reparse_point(dst):
        try:
            dst.unlink()
        except OSError:
            os.rmdir(dst)
    elif dst.is_dir():
        shutil.rmtree(dst, onerror=remove_readonly)
    elif dst.exists():
        dst.unlink()


def link_skills_to(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for s in SKILLS:
        src = XHS_OPS_ROOT / "skills" / s
        dst = target_dir / s
        if not (src / "SKILL.md").is_file():
            print(f"⚠️  跳过尚未创建的技能：{s}")
            continue
        safe_remove_target(dst)
        if IS_WINDOWS:
            # Windows 优先使用目录联接（普通用户无需管理员权限即可实时同步）
            res = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode == 0:
                print(f"🔗 已注册 Skill（Junction）：{s} -> {dst}")
            else:
                shutil.copytree(src, dst)
                print(f"📁 已注册 Skill（复制）：{s} -> {dst}")
        else:
            os.symlink(src, dst)
            print(f"🔗 已注册 Skill：{s} -> {dst}")


def safe_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def dedupe_paths(paths: list[Path]) -> list[Path]:
    """按解析后的真实路径去重（兼容 ~/.gemini/antigravity -> ~/.gemini/config 软链）。"""
    seen: set[str] = set()
    result: list[Path] = []
    for p in paths:
        try:
            key = str(p.resolve()).lower() if IS_WINDOWS else str(p.resolve())
        except Exception:
            key = str(p)
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


def get_antigravity_skill_dirs() -> list[Path]:
    home = Path.home()
    candidates = [home / ".gemini" / "antigravity" / "skills"]
    if safe_exists(home / ".gemini" / "config"):
        candidates.append(home / ".gemini" / "config" / "skills")
    return dedupe_paths(candidates)


def get_antigravity_mcp_configs() -> list[Path]:
    home = Path.home()
    candidates = [home / ".gemini" / "antigravity" / "mcp_config.json"]
    if safe_exists(home / ".gemini" / "config"):
        candidates.append(home / ".gemini" / "config" / "mcp_config.json")
    return dedupe_paths(candidates)


def merge_mcp_config(cfg_path: Path, mcp_url: str, auth_token: str) -> None:
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if cfg_path.is_file() and cfg_path.stat().st_size > 0:
        with cfg_path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded

    server_cfg: dict = {"url": mcp_url}
    if auth_token:
        server_cfg["headers"] = {"Authorization": f"Bearer {auth_token}"}

    data.setdefault("mcpServers", {})["xiaohongshu-mcp"] = server_cfg
    with cfg_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"✅ 已安全更新 Antigravity MCP 配置：{cfg_path} (xiaohongshu-mcp -> {mcp_url})")


def cmd_install_skills(env: dict[str, str], args: list[str]) -> int:
    scope = "both"
    target = "antigravity"
    i = 0
    while i < len(args):
        if args[i] == "--scope" and i + 1 < len(args):
            scope = args[i + 1]
            i += 2
        elif args[i] == "--target" and i + 1 < len(args):
            target = args[i + 1]
            i += 2
        else:
            print(f"未知参数：{args[i]}")
            print("用法：python infra/ops.py install-skills [--scope workspace|global|both] [--target antigravity|claude|codex|openclaw|all]")
            return 1

    home = Path.home()

    def install_antigravity() -> None:
        if scope in ("workspace", "both"):
            link_skills_to(XHS_WORKSPACE_DIR / ".agents" / "skills")
        if scope in ("global", "both"):
            for d in get_antigravity_skill_dirs():
                link_skills_to(d)
        mcp_url = f"http://{env['XHS_MCP_ADDR']}/mcp"
        auth_token = env.get("AUTH_TOKEN", "")
        for cfg in get_antigravity_mcp_configs():
            merge_mcp_config(cfg, mcp_url, auth_token)

    if target == "antigravity":
        install_antigravity()
    elif target == "claude":
        link_skills_to(home / ".claude" / "skills")
    elif target == "codex":
        link_skills_to(home / ".codex" / "skills")
    elif target == "openclaw":
        link_skills_to(home / ".openclaw" / "skills")
    elif target == "all":
        install_antigravity()
        for tool_dir in (".claude", ".codex", ".openclaw"):
            if (home / tool_dir).is_dir():
                link_skills_to(home / tool_dir / "skills")
    else:
        print("用法：python infra/ops.py install-skills [--scope workspace|global|both] [--target antigravity|claude|codex|openclaw|all]")
        return 1

    print("\n🎉 集成注册完成！新开会话或重载 MCP 后即可直接使用全部 5 个技能与 18 个小红书 MCP 工具。")
    return 0


def cmd_doctor(env: dict[str, str], _args: list[str]) -> int:
    passed = warned = failed = 0

    def ok(msg: str) -> None:
        nonlocal passed
        print(f"✅ {msg}")
        passed += 1

    def warn(msg: str) -> None:
        nonlocal warned
        print(f"⚠️  {msg}")
        warned += 1

    def fail(msg: str) -> None:
        nonlocal failed
        print(f"❌ {msg}")
        failed += 1

    py_cmd = "python" if IS_WINDOWS else "python3"
    print("============================================================")
    print(f"🩺 xhs-ai-ops 小红书 AI 运营工作台 · 全链路环境体检（{platform.system()} / {env['XHS_TARGET_GOARCH']}）")
    print(f"项目根目录：{XHS_OPS_ROOT}")
    print("============================================================")

    print("\n[1/5] 模块 0A：站外情报采集（Agent-Reach）")
    reach_bin = venv_bin("agent-reach")
    if reach_bin.is_file():
        rc = subprocess.run([str(reach_bin), "channels"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
        if rc == 0:
            ok(f"Agent-Reach CLI 正常（{reach_bin}）")
        else:
            fail("Agent-Reach CLI 执行异常")
    else:
        fail(f"未找到 Agent-Reach 虚拟环境（请先运行 {py_cmd} infra/ops.py bootstrap）")

    print("\n[2/5] 模块 0B：小红书站内总线（Docker 隔离容器 xiaohongshu-mcp）")
    home = Path.home()
    residual_dirs = [XHS_OPS_ROOT / "infra" / "bin"]
    if IS_MACOS:
        residual_dirs.append(home / "Library" / "Caches" / "xiaohongshu-mcp")
    elif IS_WINDOWS:
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            residual_dirs.append(Path(local_app) / "xiaohongshu-mcp")
        residual_dirs.append(home / ".cache" / "xiaohongshu-mcp")
    else:
        residual_dirs.append(home / ".cache" / "xiaohongshu-mcp")

    found_residual = [str(d) for d in residual_dirs if safe_exists(d)]
    if not found_residual:
        ok("宿主机干净：无非官方 Chromium 缓存与宿主机 MCP 二进制残留")
    else:
        warn(f"检测到宿主机存在旧缓存或二进制残留，建议清理：{', '.join(found_residual)}")

    if shutil.which("docker") and subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        ok("Docker 守护进程运行正常")
        if is_mcp_healthy(env["XHS_MCP_ADDR"]):
            ok(f"xiaohongshu-mcp 容器健康检查通过（http://{env['XHS_MCP_ADDR']}/mcp）")
        else:
            warn(f"xiaohongshu-mcp 容器尚未启动（可执行 {py_cmd} infra/ops.py start）")
    else:
        warn(f"Docker 守护进程尚未启动（请先打开 Docker Desktop，再运行 {py_cmd} infra/ops.py start）")

    if Path(env["COOKIES_HOST_PATH"]).is_file():
        ok(f"已检测到容器持久化会话文件（{env['COOKIES_HOST_PATH']}）")
    else:
        warn(f"尚未扫码登录主号（容器启动后运行 {py_cmd} infra/ops.py login 或在 AI 客户端调 get_login_qrcode）")

    print("\n[3/5] 模块 0C：多后端生图引擎（baoyu-image-gen / 原生引擎）")
    baoyu_main = XHS_OPS_ROOT / "upstream" / "baoyu-skills" / "skills" / "baoyu-image-gen" / "scripts" / "main.ts"
    if baoyu_main.is_file():
        ok("baoyu-image-gen 脚本存在")
    else:
        fail(f"缺少 baoyu-image-gen 脚本（请先运行 {py_cmd} infra/ops.py bootstrap）")

    if env.get("GOOGLE_API_KEY") or env.get("GEMINI_API_KEY"):
        ok(f"已检测到 Google Gemini 密钥（默认模型：{env.get('GOOGLE_IMAGE_MODEL', 'gemini-3-pro-image')}；免费层受限时可自动回退内置引擎或 codex-cli）")
    elif shutil.which("codex"):
        ok("已检测到本机 codex-cli，可通过 --provider codex-cli 执行参考图锚定出图")
    else:
        warn("未检测到 GOOGLE_API_KEY 或 codex-cli，可在 config/.env 配置或使用宿主内置生图引擎")

    if (XHS_OPS_ROOT / ".baoyu-skills" / "baoyu-image-gen" / "EXTEND.md").is_file():
        ok("项目级生图配置 EXTEND.md 已锁定 default_provider: google, 3:4, 2k")
    else:
        fail("缺少 .baoyu-skills/baoyu-image-gen/EXTEND.md")

    print("\n[4/5] 模块 1：人设配置与知识库骨架")
    for rel in ("config/persona.md", "config/brand-visual.md", "knowledge-base/README.md"):
        if (XHS_OPS_ROOT / rel).is_file():
            ok(f"文件就绪：{rel}")
        else:
            fail(f"缺少文件：{rel}")

    print("\n[5/5] AI 宿主集成状态（Skills 与 MCP）")
    mcp_registered: Path | None = None
    for cfg in get_antigravity_mcp_configs():
        if safe_is_file(cfg):
            try:
                if "xiaohongshu-mcp" in json.loads(cfg.read_text(encoding="utf-8")).get("mcpServers", {}):
                    mcp_registered = cfg
                    break
            except Exception:
                pass
    if mcp_registered:
        ok(f"Antigravity MCP 配置已注册 xiaohongshu-mcp（{mcp_registered}）")
    else:
        warn(f"Antigravity mcp_config.json 尚未注册 xiaohongshu-mcp（可运行 {py_cmd} infra/ops.py install-skills）")

    skill_roots = [XHS_WORKSPACE_DIR / ".agents" / "skills", *get_antigravity_skill_dirs()]
    skill_count = sum(1 for s in SKILLS if any(safe_is_file(r / s / "SKILL.md") for r in skill_roots))
    if skill_count == len(SKILLS):
        ok("5 个模块化 Skills 已全部注册就绪")
    else:
        warn(f"已注册 {skill_count}/{len(SKILLS)} 个 Skills（可运行 {py_cmd} infra/ops.py install-skills 补齐）")

    print("\n============================================================")
    print(f"📊 体检汇总：通过 {passed} 项 ｜ 待操作/警告 {warned} 项 ｜ 失败 {failed} 项")
    print("============================================================")
    return 1 if failed > 0 else 0


def print_help() -> None:
    print(
        """xhs-ai-ops 跨平台统一运维入口（Windows 11 / macOS / Linux）

用法：
  python infra/ops.py <命令> [参数...]

可用命令：
  bootstrap       拉取 5 个上游仓库至 upstream/ 并创建 .venv 安装 Agent-Reach
  build-image     本地构建原生架构 Docker 沙箱镜像（无宿主机 Go 时自动走容器多阶段编译）
  start           启动 xiaohongshu-mcp 安全沙箱容器（镜像缺失时自动构建）
  stop            停止并移除容器（保留 .runtime/mcp-data 会话）
  restart         重启容器并查看健康状态
  status          查看容器运行与健康检查状态
  logs            查看容器最近 60 行日志
  pull            拉取 compose 定义的镜像
  login           无界面二维码扫码登录小红书主号
  reach <args>    调用 Agent-Reach 站外采集（内置单主号风控护盾）
  gen-image <...> 调用 baoyu-image-gen 生成图片
  build-batch <.> 调用 baoyu-image-gen/scripts/build-batch.ts 构造批量任务
  install-skills  注册 5 个模块化 Skills 与 MCP 到 Antigravity / Claude / Codex / OpenClaw
  doctor          执行全链路 13 项健康体检
"""
    )


def main() -> int:
    configure_stdio()
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        return 0

    cmd = sys.argv[1]
    rest = sys.argv[2:]
    env = build_env()

    dispatch = {
        "bootstrap": cmd_bootstrap,
        "build-image": cmd_build_image,
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "logs": cmd_logs,
        "pull": cmd_pull,
        "login": cmd_login,
        "reach": cmd_reach,
        "gen-image": lambda e, a: run_baoyu_script(e, "main.ts", a),
        "build-batch": lambda e, a: run_baoyu_script(e, "build-batch.ts", a),
        "install-skills": cmd_install_skills,
        "doctor": cmd_doctor,
    }
    handler = dispatch.get(cmd)
    if not handler:
        print(f"❌ 未知命令：{cmd}\n")
        print_help()
        return 1
    return handler(env, rest)


if __name__ == "__main__":
    sys.exit(main())
