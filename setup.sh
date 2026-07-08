#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

export PATH="$PROJECT_DIR/wine-custom/bin:$HOME/local/usr/bin:$PATH"

WINE_VERSION="11.12"
WINE_PREFIX_DIR="$PROJECT_DIR/wine-custom"
WINE="$WINE_PREFIX_DIR/bin/wine"
WINE64="$WINE_PREFIX_DIR/bin/wine64"

PFX_DIR="$PROJECT_DIR/pfx-custom"

AVIUTL2_URL="https://spring-fragrance.mints.ne.jp/aviutl/aviutl2beta52.zip"
AVIUTL2_ZIP="aviutl2beta52.zip"

download() {
    local url="$1"
    local out="$2"
    if [[ -f "$out" ]]; then
        echo "[setup] Already present: $out"
        return 0
    fi
    echo "[setup] Downloading $out"
    curl -L -o "$out" "$url"
}

# ------------------------------------------------------------------
# 1. AviUtl2
# ------------------------------------------------------------------
download "$AVIUTL2_URL" "$AVIUTL2_ZIP"
if [[ ! -f "aviutl2.exe" ]]; then
    echo "[setup] Extracting AviUtl2"
    unzip -o "$AVIUTL2_ZIP"
fi

# ------------------------------------------------------------------
# 2. Custom Wine build
# ------------------------------------------------------------------
if [[ ! -x "$WINE" ]]; then
    echo "[setup] Custom Wine build not found at $WINE_PREFIX_DIR." >&2
    echo "[setup] Building Wine from source is slow but required for the AviUtl2 fixes." >&2
    echo "[setup] Run ./build-wine.sh first, then re-run ./setup.sh." >&2
    exit 1
fi

# ------------------------------------------------------------------
# 3. Wine prefix
# ------------------------------------------------------------------
export WINEARCH=win64
export WINEPREFIX="$PFX_DIR"

if [[ ! -d "$PFX_DIR" ]]; then
    echo "[setup] Creating Wine prefix $PFX_DIR"
    "$WINE" wineboot --init
else
    # Refresh the prefix (e.g. after rebuilding Wine with new archs).
    echo "[setup] Updating Wine prefix $PFX_DIR"
    "$WINE" wineboot --update
fi

# ------------------------------------------------------------------
# 4. Install native d3dcompiler_47
# ------------------------------------------------------------------
# AviUtl2's shader reflection needs a few interfaces that Wine's builtin
# d3dcompiler_47 does not yet implement. Use Microsoft's native 64-bit DLL.
CAB32_URL="https://download.microsoft.com/download/B/0/C/B0C80BA3-8AD6-4958-810B-6882485230B5/standalonesdk/Installers/2630bae9681db6a9f6722366f47d055c.cab"
CAB64_URL="https://download.microsoft.com/download/B/0/C/B0C80BA3-8AD6-4958-810B-6882485230B5/standalonesdk/Installers/61d57a7a82309cd161a854a6f4619e52.cab"
CAB32="$PROJECT_DIR/.cache/d3dcompiler_47/2630bae9681db6a9f6722366f47d055c.cab"
CAB64="$PROJECT_DIR/.cache/d3dcompiler_47/61d57a7a82309cd161a854a6f4619e52.cab"

if ! command -v bsdtar >/dev/null 2>&1; then
    echo "[setup] Error: bsdtar is required to install d3dcompiler_47." >&2
    exit 1
fi

mkdir -p "$PROJECT_DIR/.cache/d3dcompiler_47"
download "$CAB32_URL" "$CAB32"
download "$CAB64_URL" "$CAB64"

# Native d3dcompiler_47 is required because Wine's builtin lacks some
# shader-reflection interfaces used by AviUtl2. Extract the x64 and x86
# copies so both 64-bit AviUtl2 and 32-bit helper tools can use it.
echo "[setup] Installing native 64-bit d3dcompiler_47"
bsdtar -C "$PROJECT_DIR/.cache/d3dcompiler_47" -xf "$CAB64"
cp "$PROJECT_DIR/.cache/d3dcompiler_47/fil3585cb2ea5db13cc0838f8d06b5c9679" \
    "$PFX_DIR/drive_c/windows/system32/d3dcompiler_47.dll"

if [[ "$WINEARCH" == "win64" ]]; then
    echo "[setup] Installing native 32-bit d3dcompiler_47 (WoW64)"
    bsdtar -C "$PROJECT_DIR/.cache/d3dcompiler_47" -xf "$CAB32"
    cp "$PROJECT_DIR/.cache/d3dcompiler_47/fila319f706acfa16d6707473ebf29bdc7f" \
        "$PFX_DIR/drive_c/windows/syswow64/d3dcompiler_47.dll"
fi

# Override so Wine loads the native DLL.
"$WINE" reg add 'HKEY_CURRENT_USER\Software\Wine\DllOverrides' \
    /v d3dcompiler_47 /d native /f >/dev/null

# ------------------------------------------------------------------
# 5. Japanese fonts
# ------------------------------------------------------------------
# AviUtl2's UI uses Japanese font names (MS Gothic, Meiryo, Yu Gothic,
# etc.) which are not present in a fresh Wine prefix. Map those names
# to the system-installed Noto Sans CJK JP font.
NOTO_DIR="/usr/share/fonts/noto-cjk"
if [[ -f "$NOTO_DIR/NotoSansCJK-Regular.ttc" ]]; then
    echo "[setup] Installing Japanese fonts into the Wine prefix"
    cp "$NOTO_DIR/NotoSansCJK-Regular.ttc" \
       "$NOTO_DIR/NotoSansCJK-Bold.ttc" \
       "$PFX_DIR/drive_c/windows/Fonts/"
    "$WINE" regedit "$PROJECT_DIR/tools/japanese-fonts.reg"
else
    echo "[setup] Warning: Noto Sans CJK JP not found at $NOTO_DIR." >&2
    echo "[setup]           Japanese text may render as tofu (missing glyphs)." >&2
fi

echo "[setup] Done."
echo "[setup] Run ./launch.sh to start AviUtl2."
