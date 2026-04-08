#!/usr/bin/env bash
# ============================================================
# setup_picoclaw.sh — 自动下载/更新 picoclaw 二进制文件
# 用法: bash skills/stock-data-assistant/setup_picoclaw.sh [version]
#   version: 可选，如 "v0.2.5"，默认下载最新版
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BIN_DIR="$PROJECT_ROOT/.local/bin"
BINARY_NAME="picoclaw"

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

# 获取最新 release 版本
get_latest_version() {
    local version
    version=$(curl -sfL https://api.github.com/repos/sipeed/picoclaw/releases/latest \
        | grep '"tag_name"' \
        | sed -E 's/.*"tag_name":\s*"([^"]+)".*/\1/')
    if [[ -z "$version" ]]; then
        log_error "无法获取 picoclaw 最新版本，请检查网络连接"
        exit 1
    fi
    echo "$version"
}

# 主流程
main() {
    local TARGET_VERSION="${1:-}"
    local ARCH VERSION DOWNLOAD_URL

    # 检测架构
    ARCH=$(detect_arch)
    log_info "检测到系统架构: $ARCH"

    # 确定版本
    if [[ -n "$TARGET_VERSION" ]]; then
        # 用户指定了版本，去掉 v 前缀（如果有）
        VERSION="$TARGET_VERSION"
        [[ ! "$VERSION" =~ ^v ]] && VERSION="v$VERSION"
    else
        VERSION=$(get_latest_version)
    fi
    log_info "目标版本: $VERSION"

    # 创建 bin 目录
    mkdir -p "$BIN_DIR"

    # 构建下载 URL（picoclaw release 格式：picoclaw-{os}-{arch})
    local os_part arch_part
    case "$ARCH" in
        linux-amd64)    os_part="linux"; arch_part="x86_64" ;;
        linux-arm64)    os_part="linux"; arch_part="aarch64" ;;
        linux-riscv64)  os_part="linux"; arch_part="riscv64" ;;
    esac

    # picoclaw 的 release 文件名格式: picoclaw-linux-x86_64 等
    local FILENAME="picoclaw-${os_part}-${arch_part}"
    DOWNLOAD_URL="https://github.com/sipeed/picoclaw/releases/download/${VERSION}/${FILENAME}"

    log_info "下载地址: $DOWNLOAD_URL"
    log_info "目标路径: $BIN_DIR/$BINARY_NAME"

    # 下载
    TMPFILE=$(mktemp)
    trap 'rm -f "$TMPFILE"' EXIT

    log_info "正在下载 picoclaw ${VERSION} ..."
    if ! curl -fSL --progress-bar -o "$TMPFILE" "$DOWNLOAD_URL"; then
        rm -f "$TMPFILE"
        log_error "下载失败！请手动检查: $DOWNLOAD_URL"
        log_error "可能需要从 GitHub Releases 页面确认正确的文件名"
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
