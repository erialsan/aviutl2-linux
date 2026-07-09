#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# AviUtl2 + Proton GE + DXVK standalone launcher
# No Steam required. Uses GE's wine + DXVK v2.7.1 (Vulkan).
#
# Catalog integration:
#   --catalog <command> [args]  — Run catalog CLI tool instead of launching
#   CATALOG_AUTO_CHECK=1       — Check for package updates after launch
#
#
# Prerequisite: Proton GE must be installed first.
#   mkdir -p ~/.local/share/Steam/compatibilitytools.d
#   curl -L -o GE-Proton11-1.tar.gz https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton11-1/GE-Proton11-1.tar.gz
#   tar -xzf GE-Proton11-1.tar.gz -C ~/.local/share/Steam/compatibilitytools.d/
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# --- Catalog integration ---
CATALOG_CLI="$PROJECT_DIR/tools/catalog/catalog-cli.py"

# If --catalog is passed, run catalog command instead of launching AviUtl2
if [[ "${1:-}" == "--catalog" ]]; then
    shift
    export WINEPREFIX="${WINEPREFIX:-$PROJECT_DIR/pfx-ge/pfx}"
    export AVIUTL2_ROOT="$PROJECT_DIR"
    exec python3 "$CATALOG_CLI" "$@"
fi

# --- Proton GE path ---
GE_DIR="${GE_DIR:-$HOME/.local/share/Steam/compatibilitytools.d/GE-Proton11-1}"

if [[ ! -d "$GE_DIR/files/lib/wine" ]]; then
    echo "[launch-ge] Proton GE not found at: $GE_DIR" >&2
    echo "[launch-ge] Download: https://github.com/GloriousEggroll/proton-ge-custom/releases" >&2
    echo "[launch-ge] Extract to: ~/.local/share/Steam/compatibilitytools.d/" >&2
    exit 1
fi

if [[ ! -f "aviutl2.exe" ]]; then
    echo "[launch-ge] aviutl2.exe not found. Please run ./setup.sh first." >&2
    exit 1
fi

GE_WINE="$GE_DIR/files/lib/wine/x86_64-unix/wine"
GE_WINESERVER="$GE_DIR/files/bin/wineserver"
GE_DXVK="$GE_DIR/files/lib/wine/dxvk"

# --- Prefix ---
PFX_DIR="${PFX_DIR:-$PROJECT_DIR/pfx-ge}"
PFX="$PFX_DIR/pfx"

# --- First-time prefix setup ---
if [[ ! -d "$PFX" ]]; then
    echo "[launch-ge] Initializing Proton GE prefix..."
    export STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.local/share/Steam"
    export STEAM_COMPAT_DATA_PATH="$PFX_DIR"
    export STEAM_COMPAT_APP_ID="0"
    export UMU_ID="aviutl2"
    timeout 30 "$GE_DIR/proton" run "$PROJECT_DIR/aviutl2.exe" 2>/dev/null || true
    echo "[launch-ge] Prefix initialized."
fi

# --- Install DXVK DLLs into prefix ---
copy_dxvk() {
    local arch="$1"      # x86_64-windows or i386-windows
    local dest="$2"      # system32 or syswow64
    mkdir -p "$PFX/drive_c/windows/$dest"
    for dll in d3d11 dxgi d3d10core; do
        if [[ -f "$GE_DXVK/$arch/$dll.dll" ]]; then
            cp "$GE_DXVK/$arch/$dll.dll" "$PFX/drive_c/windows/$dest/" 2>/dev/null || true
        fi
    done
}

# Only copy if the DXVK version changed or files are missing
DXVK_VER=$(cat "$GE_DXVK/version" 2>/dev/null || echo "unknown")
DXVK_STAMP="$PFX/.dxvk-version"
if [[ "$(cat "$DXVK_STAMP" 2>/dev/null)" != "$DXVK_VER" ]]; then
    echo "[launch-ge] Installing DXVK $DXVK_VER..."
    copy_dxvk "x86_64-windows" "system32"
    copy_dxvk "i386-windows" "syswow64"
    echo "$DXVK_VER" > "$DXVK_STAMP"
fi

# --- Install native d3dcompiler_47 (if not already present, e.g. from setup.sh) ---
mkdir -p "$PFX/drive_c/windows/system32" "$PFX/drive_c/windows/syswow64"
D3D_DEST64="$PFX/drive_c/windows/system32/d3dcompiler_47.dll"
D3D_DEST32="$PFX/drive_c/windows/syswow64/d3dcompiler_47.dll"
if [[ ! -f "$D3D_DEST64" ]]; then
    CACHE_DIR="$PROJECT_DIR/.cache/d3dcompiler_47"
    mkdir -p "$CACHE_DIR" "$(dirname "$D3D_DEST64")" "$(dirname "$D3D_DEST32")"
    CAB64_URL="https://download.microsoft.com/download/B/0/C/B0C80BA3-8AD6-4958-810B-6882485230B5/standalonesdk/Installers/61d57a7a82309cd161a854a6f4619e52.cab"
    CAB32_URL="https://download.microsoft.com/download/B/0/C/B0C80BA3-8AD6-4958-810B-6882485230B5/standalonesdk/Installers/2630bae9681db6a9f6722366f47d055c.cab"
    CAB64="$CACHE_DIR/61d57a7a82309cd161a854a6f4619e52.cab"
    CAB32="$CACHE_DIR/2630bae9681db6a9f6722366f47d055c.cab"
    if command -v bsdtar >/dev/null 2>&1; then
        echo "[launch-ge] Downloading native d3dcompiler_47..."
        curl -fL -o "$CAB64" "$CAB64_URL" 2>/dev/null || true
        curl -fL -o "$CAB32" "$CAB32_URL" 2>/dev/null || true
        if [[ -f "$CAB64" ]]; then
            bsdtar -C "$CACHE_DIR" -xf "$CAB64" 2>/dev/null || true
            cp "$CACHE_DIR/fil3585cb2ea5db13cc0838f8d06b5c9679" "$D3D_DEST64" 2>/dev/null || true
        fi
        if [[ -f "$CAB32" ]]; then
            bsdtar -C "$CACHE_DIR" -xf "$CAB32" 2>/dev/null || true
            cp "$CACHE_DIR/fila319f706acfa16d6707473ebf29bdc7f" "$D3D_DEST32" 2>/dev/null || true
        fi
    fi
fi

# --- Set up DXVK DLL overrides in registry ---
setup_overrides() {
    local wine="$1"
    local pfx="$2"
    for dll in d3d11 d3d10core dxgi; do
        "$wine" reg add 'HKEY_CURRENT_USER\Software\Wine\DllOverrides' \
            /v "$dll" /d native,builtin /f 2>/dev/null || true
    done
    "$wine" reg add 'HKEY_CURRENT_USER\Software\Wine\DllOverrides' \
        /v d3dcompiler_47 /d native /f 2>/dev/null || true
}

# --- Configure encoder paths for x264guiEx/x265guiEx ---
setup_encoders() {
    local plugin_dir="$PFX/drive_c/ProgramData/aviutl2/Plugin"
    local exe_dir="$plugin_dir/exe_files"

    # x264 path
    if [[ -f "$plugin_dir/x264guiEx.conf" ]]; then
        if ! grep -q "x264_path" "$plugin_dir/x264guiEx.conf" 2>/dev/null; then
            echo "x264_path=C:\\ProgramData\\aviutl2\\Plugin\\exe_files\\x264_3223_x64.exe" >> "$plugin_dir/x264guiEx.conf"
        fi
    fi

    # x265 path
    if [[ -f "$plugin_dir/x265guiEx.conf" ]]; then
        if ! grep -q "x265_path" "$plugin_dir/x265guiEx.conf" 2>/dev/null; then
            echo "x265_path=C:\\ProgramData\\aviutl2\\Plugin\\exe_files\\x265_4.1+190_x64.exe" >> "$plugin_dir/x265guiEx.conf"
        fi
    fi
}

# --- Environment ---
export WINEPREFIX="$PFX"
export WINEDLLOVERRIDES="d3d11,dxgi,d3d10core=n;d3dcompiler_47=n"
# Disable DXVK hardware YCbCr sampler (Intel GPU U/V swap workaround)
# Forces software YUV→RGB conversion for NV12/YUY2 shader resource views
export DXVK_D3D11_DISABLE_YCBCR=1
export DXVK_VIDEO_USE_VK_FORMAT=0
export DISPLAY="${DISPLAY:-:1}"

# Library path for GE's wine-staging
export LD_LIBRARY_PATH="$GE_DIR/files/lib64:$GE_DIR/files/lib:$GE_DIR/files/lib/wine/x86_64-unix:$GE_DIR/files/lib/wine/i386-unix:${LD_LIBRARY_PATH:-}"

# --- Apply registry overrides ---
setup_overrides "$GE_WINE" "$PFX"
setup_encoders
# Export AVIUTL2_ROOT for catalog integration
export AVIUTL2_ROOT="$PROJECT_DIR"

echo "[launch-ge] Wine:  wine-staging (Proton GE)"
echo "[launch-ge] DXVK:  $(cat "$GE_DXVK/version" 2>/dev/null || echo 'v2.7.1')"
echo "[launch-ge] Prefix: $PFX"
echo "[launch-ge] Starting AviUtl2..."
echo "[launch-ge] Note: 'D3D RDMs not supported' dialog may appear — press Enter 2x or use dismiss-dialogs.py"
# Start AviUtl2 in background
"$GE_WINE" "$PROJECT_DIR/aviutl2.exe" "$@" &

# Optional: check for catalog updates after launch (non-blocking)
if [[ -n "${CATALOG_AUTO_CHECK:-}" ]] && [[ -f "$CATALOG_CLI" ]]; then
    echo "[launch-ge] Checking for package updates..."
    python3 "$CATALOG_CLI" update 2>&1 | sed 's/^/[catalog] /' &
fi
AVIUTL2_PID=$!

# Auto-dismiss startup dialogs
sleep 3
for i in $(seq 1 5); do
    python3 "$PROJECT_DIR/tools/dismiss-dialogs.py" --display "${DISPLAY:-:1}" --count 1 --delay 0.3 2>/dev/null || true
    sleep 0.5
done

# Wait for AviUtl2 to exit
wait $AVIUTL2_PID 2>/dev/null || true
