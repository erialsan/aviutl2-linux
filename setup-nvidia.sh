#!/usr/bin/env bash
# ============================================================
# NVIDIA GPU 用ライブラリ (NVENC/NVCUDA/NVAPI) を
# Proton GE + Wine prefix にインストールします。
#
# 必要に応じて:
#   ./setup-nvidia.sh         通常インストール
#   ./setup-nvidia.sh --force 再インストール
# ============================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

GE_DIR="${GE_DIR:-$HOME/.local/share/Steam/compatibilitytools.d/GE-Proton11-1}"
PFX_DIR="${PFX_DIR:-$PROJECT_DIR/pfx-ge}"
CACHE_DIR="$PROJECT_DIR/.cache/nvidia-libs"
RELEASE="v1.0.2"
TARBALL="nvidia-libs-${RELEASE}.tar.xz"
URL="https://github.com/SveSop/nvidia-libs/releases/download/${RELEASE}/${TARBALL}"

info()  { echo "[nvidia] $*"; }
warn()  { echo "[nvidia] Warning: $*" >&2; }
error() { echo "[nvidia] Error: $*" >&2; exit 1; }

# ── NVIDIA GPU の検出 ──
detect_nvidia() {
    if command -v nvidia-smi >/dev/null 2>&1; then
        return 0
    fi
    if command -v lspci >/dev/null 2>&1 && lspci | grep -qi "VGA.*NVIDIA"; then
        return 0
    fi
    return 1
}

# ── ダウンロード・展開 ──
download_extract() {
    mkdir -p "$CACHE_DIR"
    local tarball_path="$CACHE_DIR/$TARBALL"
    local extract_dir="$CACHE_DIR/nvidia-libs-${RELEASE}"

    if [[ ! -d "$extract_dir/x64" ]] || [[ "${1:-}" == "--force" ]]; then
        if [[ ! -f "$tarball_path" ]]; then
            info "ダウンロード: $TARBALL ..."
            curl -fL -o "$tarball_path" "$URL" || { rm -f "$tarball_path"; error "ダウンロード失敗"; }
        fi
        info "展開中..."
        rm -rf "$extract_dir"
        mkdir -p "$extract_dir"
        tar -xJf "$tarball_path" -C "$CACHE_DIR"
    fi
    echo "$extract_dir"
}

# ── Proton GE へのインストール ──
install_proton() {
    local src="$1"

    if [[ ! -d "$GE_DIR/files/lib/wine" ]]; then
        warn "Proton GE が見つかりません ($GE_DIR)。スキップ"
        return
    fi

    # DLL を Proton GE の wine フォルダにコピー
    local wine_dir="$GE_DIR/files/lib/wine"
    info "Proton GE にインストール: $GE_DIR"

    # 64-bit DLLs
    local dest64="$wine_dir/x86_64-windows"
    mkdir -p "$dest64"
    for dll in "$src/x64/"*.dll; do
        cp -f "$dll" "$dest64/" 2>/dev/null || true
    done

    # NVML (wine-native .so + .dll)
    if [[ -d "$src/x64/wine" ]]; then
        cp -rf "$src/x64/wine/"* "$wine_dir/" 2>/dev/null || true
    fi

    # 32-bit NVAPI
    local dest32="$wine_dir/x86_32-windows"
    mkdir -p "$dest32"
    if [[ -f "$src/x32/nvapi.dll" ]]; then
        cp -f "$src/x32/nvapi.dll" "$dest32/" 2>/dev/null || true
    fi

    # Vulkan Reflex layer
    if [[ -d "$src/layer" ]]; then
        local vk_layer="$GE_DIR/files/share/vulkan/implicit_layer.d"
        mkdir -p "$vk_layer"
        cp -f "$src/layer/"* "$vk_layer/" 2>/dev/null || true
    fi

    info "Proton GE へのインストール完了"
}

# ── Wine prefix へのインストール ──
install_prefix() {
    local src="$1"
    local pfx="$PFX_DIR/pfx"

    if [[ ! -d "$pfx" ]]; then
        warn "Wine prefix が見つかりません ($pfx)。先に ./setup.sh を実行してください"
        return
    fi

    local sys32="$pfx/drive_c/windows/system32"
    local syswow="$pfx/drive_c/windows/syswow64"
    mkdir -p "$sys32" "$syswow"

    info "Wine prefix にインストール: $pfx"

    # 64-bit DLLs → system32
    for dll in "$src/x64/"*.dll; do
        cp -f "$dll" "$sys32/" 2>/dev/null || true
    done

    # 32-bit NVAPI → syswow64
    if [[ -f "$src/x32/nvapi.dll" ]]; then
        cp -f "$src/x32/nvapi.dll" "$syswow/" 2>/dev/null || true
    fi

    # NVML wine-native (.so) は Proton GE 側に入れるので prefix には不要

    info "Wine prefix へのインストール完了"
}

# ── レジストリオーバーライド ──
setup_registry() {
    local pfx="$PFX_DIR/pfx"
    local wine_bin="$GE_DIR/files/lib/wine/x86_64-unix/wine"

    if [[ ! -x "$wine_bin" ]] || [[ ! -d "$pfx" ]]; then
        return
    fi

    info "レジストリオーバーライドを設定..."
    export WINEPREFIX="$pfx"
    for dll in nvapi nvapi64 nvcuda nvcuvid nvencodeapi nvencodeapi64 nvofapi64 nvml; do
        "$wine_bin" reg add 'HKEY_CURRENT_USER\Software\Wine\DllOverrides' \
            /v "$dll" /d native,builtin /f 2>/dev/null || true
    done
}

# ── 環境変数のヘルプ表示 ──
print_env() {
    cat <<EOF

[nvidia] 以下の環境変数を設定すると NVEnc が有効になります:
  export DXVK_ENABLE_NVAPI=1
  export PROTON_ENABLE_NVAPI=1

起動時に自動適用するには:
  echo 'export DXVK_ENABLE_NVAPI=1' >> ~/.bashrc
  echo 'export PROTON_ENABLE_NVAPI=1' >> ~/.bashrc

または launch-ge.sh 内で設定することも可能です。
EOF
}

# ── メイン ──

if ! detect_nvidia; then
    info "NVIDIA GPU は検出されませんでした。"
    info "このスクリプトは NVIDIA GPU 搭載環境でのみ必要です。"
    exit 0
fi

info "NVIDIA GPU を検出しました。"
FORCE="${1:-}"
SRC=$(download_extract "$FORCE")
install_proton "$SRC"
install_prefix "$SRC"
setup_registry
print_env

info "完了。./launch-ge.sh で NVEnc (nvencodeapi64.dll) が利用可能になります。"
