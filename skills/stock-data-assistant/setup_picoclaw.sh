#!/usr/bin/env bash
# ============================================================
# setup_picoclaw.sh — 自动下载/更新 picoclaw 二进制文件
# 用法: bash skills/stock-data-assistant/setup_picoclaw.sh [version]
#   version: 可选，如 "v0.2.5"，默认下载最新版
#
# 国内镜像支持:
#   默认按顺序尝试: ghfast.top -> ghproxy.cc -> GitHub 直连
#   可通过 PICOCLAW_MIRROR 环境变量指定镜像前缀:
#     PICOCLAW_MIRROR="https://ghfast.top" bash setup_picoclaw.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BIN_DIR="$PROJECT_ROOT/.local/bin"
BINARY_NAME="picoclaw"

# 国内镜像列表（按优先级排列）
DEFAULT_MIRRORS=(
    "https://ghfast.top"
    "https://ghproxy.cc"
    "DIRECT"  # GitHub 直连
)
GITHUB_BASE="https://github.com"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# 检测系统架构
detect_arch() {
    local arch uname_arch
    uname_arch=$(uname -m)
    case "$uname_arch" in
        x86_64|amd64)  arch="linux-amd64" ;;
        aarch64|arm64) arch="linux-arm64" ;;
        riscv64)       arch="linux-riscv64" ;;
        *)
            log_error "不支持的架构: $uname_arch (仅支持 x86_64 / aarch64 / riscv64)"
            exit 1
            ;;
    esac
    echo "$arch"
}

# 获取最新 release 版本（支持镜像 fallback）
get_latest_version() {
    local version

    # 尝试 GitHub API（可能需要镜像）
    local api_url="https://api.github.com/repos/sipeed/picoclaw/releases/latest"

    # 先试直连
    version=$(curl -sfL --max-time 10 "$api_url" 2>/dev/null \
        | grep '"tag_name"' \
        | sed -E 's/.*"tag_name":\s*"([^"]+)".*/\1/' || true)

    # 直连失败则用镜像代理 API
    if [[ -z "$version" ]]; then
        log_warn "GitHub API 直连失败，尝试镜像..."
        for mirror in "${DEFAULT_MIRRORS[@]}"; do
            [[ "$mirror" == "DIRECT" ]] && continue
            local mirrored_api="${mirror}/${api_url}"
            version=$(curl -sfL --max-time 15 "$mirrored_api" 2>/dev/null \
                | grep '"tag_name"' \
                | sed -E 's/.*"tag_name":\s*"([^"]+)".*/\1/' || true)
            if [[ -n "$version" ]]; then
                log_info "通过镜像 $mirror 获取版本成功"
                break
            fi
        done
    fi

    if [[ -z "$version" ]]; then
        log_error "无法获取 picoclaw 最新版本，请检查网络连接"
        log_error "也可指定版本号: bash setup_picoclaw.sh v0.2.6"
        exit 1
    fi
    echo "$version"
}

# 尝试通过多个镜像下载
download_with_mirrors() {
    local github_path="$1"  # e.g. /sipeed/picoclaw/releases/download/v0.2.6/picoclaw-linux-x86_64
    local output_file="$2"

    # 如果用户指定了镜像，优先使用
    local mirrors=()
    if [[ -n "${PICOCLAW_MIRROR:-}" ]]; then
        mirrors=("$PICOCLAW_MIRROR" "DIRECT")
    else
        mirrors=("${DEFAULT_MIRRORS[@]}")
    fi

    for mirror in "${mirrors[@]}"; do
        local url
        if [[ "$mirror" == "DIRECT" ]]; then
            url="${GITHUB_BASE}${github_path}"
            log_info "尝试 GitHub 直连: $url"
        else
            url="${mirror}/${GITHUB_BASE}${github_path}"
            log_info "尝试镜像 $mirror: $url"
        fi

        if curl -fSL --max-time 120 --progress-bar -o "$output_file" "$url" 2>/dev/null; then
            log_info "下载成功 (via ${mirror})"
            return 0
        fi
        log_warn "下载失败 (${mirror})，尝试下一个源..."
    done

    return 1
}

# 主流程
main() {
    local TARGET_VERSION="${1:-}"
    local ARCH VERSION

    # 检测架构
    ARCH=$(detect_arch)
    log_info "检测到系统架构: $ARCH"

    # 确定版本
    if [[ -n "$TARGET_VERSION" ]]; then
        VERSION="$TARGET_VERSION"
        [[ ! "$VERSION" =~ ^v ]] && VERSION="v$VERSION"
    else
        VERSION=$(get_latest_version)
    fi
    log_info "目标版本: $VERSION"

    # 创建 bin 目录
    mkdir -p "$BIN_DIR"

    # 构建下载路径（picoclaw release 格式：picoclaw-{os}-{arch})
    local os_part arch_part
    case "$ARCH" in
        linux-amd64)    os_part="linux"; arch_part="x86_64" ;;
        linux-arm64)    os_part="linux"; arch_part="aarch64" ;;
        linux-riscv64)  os_part="linux"; arch_part="riscv64" ;;
    esac

    local FILENAME="picoclaw-${os_part}-${arch_part}"
    local GITHUB_PATH="/sipeed/picoclaw/releases/download/${VERSION}/${FILENAME}"

    log_info "目标路径: $BIN_DIR/$BINARY_NAME"

    # 下载（带镜像 fallback）
    TMPFILE=$(mktemp)
    trap 'rm -f "$TMPFILE"' EXIT

    log_info "正在下载 picoclaw ${VERSION} ..."
    if ! download_with_mirrors "$GITHUB_PATH" "$TMPFILE"; then
        rm -f "$TMPFILE"
        log_error "所有下载源均失败！"
        log_error "请手动从以下地址下载:"
        log_error "  GitHub: https://github.com/sipeed/picoclaw/releases"
        log_error "  镜像:   https://ghfast.top/https://github.com/sipeed/picoclaw/releases"
        exit 1
    fi

    # 设置可执行权限并安装
    chmod +x "$TMPFILE"
    mv -f "$TMPFILE" "$BIN_DIR/$BINARY_NAME"

    # 验证
    INSTALLED_VERSION=$("$BIN_DIR/$BINARY_NAME" --version 2>/dev/null || echo "unknown")
    log_info "✅ picoclaw 已安装到 $BIN_DIR/$BINARY_NAME (版本: $INSTALLED_VERSION)"

    # 提示加入 PATH
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        log_warn ""
        log_warn "⚠️  $BIN_DIR 不在 PATH 中，建议执行："
        log_warn "    export PATH=\"$BIN_DIR:\$PATH\""
        log_warn "    或将其添加到 ~/.bashrc / ~/.zshrc 中"
    fi

    echo ""
    log_info "下一步: 运行 generate_picoclaw_config.py 生成配置文件"
    log_info "      然后运行 start_wechat_bridge.sh 启动微信联动服务"
}

main "$@"
