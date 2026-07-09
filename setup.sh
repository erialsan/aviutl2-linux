#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# AviUtl2 + Proton GE セットアップスクリプト
#
# 以下の処理を行います:
#   1. AviUtl2 のダウンロード
#   2. Proton GE の確認
#   3. Wine プレフィックスの作成 (Proton GE 経由)
#   4. ネイティブ d3dcompiler_47.dll のインストール
#   5. 日本語フォントの設定
#
# 使用方法:
#   ./setup.sh
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ── 設定 ──

AVIUTL2_URL="${AVIUTL2_URL:-https://spring-fragrance.mints.ne.jp/aviutl/aviutl2beta52.zip}"
AVIUTL2_ZIP="${AVIUTL2_ZIP:-aviutl2beta52.zip}"
GE_DIR="${GE_DIR:-$HOME/.local/share/Steam/compatibilitytools.d/GE-Proton11-1}"
PFX_DIR="${PFX_DIR:-$PROJECT_DIR/pfx-ge}"

CACHE_DIR="$PROJECT_DIR/.cache/d3dcompiler_47"
CAB32_URL="https://download.microsoft.com/download/B/0/C/B0C80BA3-8AD6-4958-810B-6882485230B5/standalonesdk/Installers/2630bae9681db6a9f6722366f47d055c.cab"
CAB64_URL="https://download.microsoft.com/download/B/0/C/B0C80BA3-8AD6-4958-810B-6882485230B5/standalonesdk/Installers/61d57a7a82309cd161a854a6f4619e52.cab"
NOTO_DIR="/usr/share/fonts/noto-cjk"

# ── ヘルパー ──

info()  { echo "[setup] $*"; }
warn()  { echo "[setup] Warning: $*" >&2; }
error() { echo "[setup] Error: $*" >&2; exit 1; }

download() {
    local url="$1" out="$2"
    if [[ -f "$out" ]]; then
        info "Already present: $out"
        return 0
    fi
    info "Downloading $out ..."
    curl -fL -o "$out" "$url" || { rm -f "$out"; error "Download failed: $url"; }
}

need_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        error "Required command not found: $1"
    fi
}

# ── 1. AviUtl2 ──

if [[ ! -f "aviutl2.exe" ]]; then
    info "AviUtl2 が見つかりません。ダウンロードします..."
    download "$AVIUTL2_URL" "$AVIUTL2_ZIP"
    info "展開中..."
    unzip -o "$AVIUTL2_ZIP"
    info "aviutl2.exe を入手しました"
else
    info "aviutl2.exe は既に存在します"
fi

# ── 2. Proton GE の確認 ──

if [[ ! -d "$GE_DIR/files/lib/wine" ]]; then
    cat >&2 <<EOF
[setup] Proton GE が見つかりません: $GE_DIR
[setup]
[setup] 以下の手順でインストールしてください:
[setup]
[setup]   mkdir -p ~/.local/share/Steam/compatibilitytools.d
[setup]   cd ~/.local/share/Steam/compatibilitytools.d
[setup]   curl -L -o GE-Proton11-1.tar.gz https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton11-1/GE-Proton11-1.tar.gz
[setup]   tar -xzf GE-Proton11-1.tar.gz
[setup]
[setup] その後、再度 ./setup.sh を実行してください。
EOF
    exit 1
fi

info "Proton GE: $GE_DIR"

# ── 3. Wine プレフィックスの作成 ──

PFX="$PFX_DIR/pfx"

if [[ ! -d "$PFX" ]]; then
    info "Wine プレフィックスを作成中 (初回は時間がかかる場合があります)..."
    mkdir -p "$PFX_DIR"
    export STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.local/share/Steam"
    export STEAM_COMPAT_DATA_PATH="$PFX_DIR"
    export STEAM_COMPAT_APP_ID="0"
    export UMU_ID="aviutl2"
    timeout 60 "$GE_DIR/proton" run "$PROJECT_DIR/aviutl2.exe" 2>/dev/null || true
    info "プレフィックスを作成しました: $PFX"
else
    info "プレフィックスは既に存在します: $PFX"
fi

# ── 4. ネイティブ d3dcompiler_47 のインストール ──

need_cmd bsdtar

SYSTEM32="$PFX/drive_c/windows/system32"
SYSWOW64="$PFX/drive_c/windows/syswow64"
D3D_DEST64="$SYSTEM32/d3dcompiler_47.dll"
D3D_DEST32="$SYSWOW64/d3dcompiler_47.dll"

if [[ -f "$D3D_DEST64" ]]; then
    info "d3dcompiler_47.dll は既にインストールされています"
else
    info "d3dcompiler_47.dll をダウンロード・インストールします..."

    mkdir -p "$CACHE_DIR" "$SYSTEM32" "$SYSWOW64"

    CAB32="$CACHE_DIR/2630bae9681db6a9f6722366f47d055c.cab"
    CAB64="$CACHE_DIR/61d57a7a82309cd161a854a6f4619e52.cab"

    download "$CAB32_URL" "$CAB32"
    download "$CAB64_URL" "$CAB64"

    info "64-bit d3dcompiler_47 を展開..."
    bsdtar -C "$CACHE_DIR" -xf "$CAB64"
    cp "$CACHE_DIR/fil3585cb2ea5db13cc0838f8d06b5c9679" "$D3D_DEST64"

    info "32-bit d3dcompiler_47 を展開 (WoW64)..."
    bsdtar -C "$CACHE_DIR" -xf "$CAB32"
    cp "$CACHE_DIR/fila319f706acfa16d6707473ebf29bdc7f" "$D3D_DEST32"

    info "d3dcompiler_47.dll をインストールしました"
fi

# ── 5. カタログ CLI の依存関係 ──

CATALOG_CLI="$PROJECT_DIR/tools/catalog/catalog-cli.py"
if [[ -f "$CATALOG_CLI" ]]; then
    info "カタログ CLI の依存関係を確認中..."

    # Python 3.10+
    if command -v python3 >/dev/null 2>&1; then
        pyver=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
        if [[ "$(echo "$pyver" | cut -d. -f1)" -lt 3 ]] || { [[ "$(echo "$pyver" | cut -d. -f1)" -eq 3 ]] && [[ "$(echo "$pyver" | cut -d. -f2)" -lt 10 ]]; }; then
            warn "Python 3.10+ が必要です (現在: $(python3 --version 2>&1))"
            warn "カタログ機能を使用するにはアップグレードしてください"
        else
            info "Python: $(python3 --version 2>&1)"
        fi
    else
        warn "python3 が見つかりません。カタログ機能を使用するには python 3.10+ をインストールしてください"
    fi

    # システムツール (なくてもカタログ参照は可能)
    for cmd in xxh128sum zstd; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            warn "$cmd が見つかりません。パッケージインストール/検出には以下が必要:"
            warn "  sudo pacman -S xxhash zstd"
        fi
    done

    # 7z (SFX アーカイブの展開に必要)
    if ! command -v 7z >/dev/null 2>&1 && ! python3 -c "import py7zr" 2>/dev/null; then
        warn "7z または py7zr が見つかりません。一部のパッケージ (QSVEnc, NVEnc など) のインストールに必要:"
        warn "  sudo pacman -S 7zip"
        warn "  または: pip install py7zr"
    fi

    # カタログ設定ディレクトリを作成
    CATALOG_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/aviutl2-catalog"
    mkdir -p "$CATALOG_CONFIG_DIR"
    info "カタログ設定: $CATALOG_CONFIG_DIR"
fi

# ── 6. NVIDIA GPU 用ライブラリ (NVEnc/CUDA) ──

NVIDIA_SCRIPT="$PROJECT_DIR/setup-nvidia.sh"
if [[ -f "$NVIDIA_SCRIPT" ]] && command -v lspci >/dev/null 2>&1 && lspci 2>/dev/null | grep -qi "VGA.*NVIDIA"; then
    info "NVIDIA GPU を検出しました。NVEnc ライブラリをセットアップします..."
    bash "$NVIDIA_SCRIPT" 2>&1 | sed 's/^/  /'
    info "NVEnc セットアップ完了"
elif [[ -f "$NVIDIA_SCRIPT" ]] && command -v nvidia-smi >/dev/null 2>&1; then
    info "NVIDIA GPU を検出しました (nvidia-smi)。NVEnc ライブラリをセットアップします..."
    bash "$NVIDIA_SCRIPT" 2>&1 | sed 's/^/  /'
    info "NVEnc セットアップ完了"
fi

# ── 7. 日本語フォント ──

if [[ -d "$NOTO_DIR" ]] && ls "$NOTO_DIR"/NotoSansCJK-*.ttc >/dev/null 2>&1; then
    FONTS_DIR="$PFX/drive_c/windows/Fonts"
    mkdir -p "$FONTS_DIR"
    if [[ ! -f "$FONTS_DIR/NotoSansCJK-Regular.ttc" ]]; then
        info "日本語フォントを Wine プレフィックスにインストール..."
        cp "$NOTO_DIR"/NotoSansCJK-*.ttc "$FONTS_DIR/"
    else
        info "日本語フォントは既にインストールされています"
    fi

    REG_FILE="$PROJECT_DIR/tools/japanese-fonts.reg"
    if [[ -f "$REG_FILE" ]]; then
        export WINEPREFIX="$PFX"
        "$GE_DIR/files/lib/wine/x86_64-unix/wine" regedit "$REG_FILE" 2>/dev/null || true
    fi
else
    warn "Noto Sans CJK JP フォントが見つかりません ($NOTO_DIR)"
    warn "日本語が正しく表示されない可能性があります"
    warn "インストール: sudo pacman -S noto-fonts-cjk"
fi

# ── 完了 ──

info "セットアップが完了しました。"
info "AviUtl2 起動:       ./launch-ge.sh"
info "カタログ CLI:        ./catalog --help"
info "カタログ GUI:        ./catalog-gui/run.sh   (要 bun + Rust)"
