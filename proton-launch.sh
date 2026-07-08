#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# AviUtl2 + Proton (Experimental / GE) launcher
# Prefers GE-Proton11-1 if available, falls back to Proton Experimental.
# Steam is NOT required — uses UMU_ID for standalone mode.
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f "aviutl2.exe" ]]; then
    echo "[proton-launch] Missing aviutl2.exe. Please run ./setup.sh first." >&2
    exit 1
fi

STEAM_ROOT="${HOME}/.local/share/Steam"

# --- Find Proton ---
PROTON_DIR=""
for candidate in \
    "$STEAM_ROOT/compatibilitytools.d/GE-Proton11-1" \
    "$STEAM_ROOT/compatibilitytools.d/GE-Proton"* \
    "$STEAM_ROOT/steamapps/common/Proton - Experimental" \
    "$STEAM_ROOT/steamapps/common/Proton 11.0" \
    "$STEAM_ROOT/steamapps/common/Proton 10.0" \
    "$STEAM_ROOT/steamapps/common/Proton Hotfix"; do
    if [[ -x "$candidate/proton" ]]; then
        PROTON_DIR="$candidate"
        break
    fi
done

if [[ -z "$PROTON_DIR" ]]; then
    echo "[proton-launch] No Proton installation found." >&2
    echo "[proton-launch] Install GE-Proton11-1 to: ~/.local/share/Steam/compatibilitytools.d/" >&2
    echo "[proton-launch]   curl -L -o GE-Proton11-1.tar.gz https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton11-1/GE-Proton11-1.tar.gz" >&2
    echo "[proton-launch]   tar -xzf GE-Proton11-1.tar.gz -C ~/.local/share/Steam/compatibilitytools.d/" >&2
    exit 1
fi

# --- Prefix ---
PFX_DIR="${PFX_DIR:-$PROJECT_DIR/pfx-proton}"

# --- Install native d3dcompiler_47 ---
mkdir -p "$PFX_DIR/pfx/drive_c/windows/system32" "$PFX_DIR/pfx/drive_c/windows/syswow64"
if [[ ! -f "$PFX_DIR/pfx/drive_c/windows/system32/d3dcompiler_47.dll" ]]; then
    if [[ -f "$PROJECT_DIR/pfx-custom/drive_c/windows/system32/d3dcompiler_47.dll" ]]; then
        cp "$PROJECT_DIR/pfx-custom/drive_c/windows/system32/d3dcompiler_47.dll" \
            "$PFX_DIR/pfx/drive_c/windows/system32/" 2>/dev/null || true
        cp "$PROJECT_DIR/pfx-custom/drive_c/windows/syswow64/d3dcompiler_47.dll" \
            "$PFX_DIR/pfx/drive_c/windows/syswow64/" 2>/dev/null || true
    fi
fi

# --- Environment (standalone mode via UMU_ID) ---
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$PFX_DIR"
export STEAM_COMPAT_APP_ID="0"
export UMU_ID="aviutl2"
export WINEDLLOVERRIDES="d3dcompiler_47=n"
export DISPLAY="${DISPLAY:-:1}"

if [[ "${1:-}" == "--debug" ]]; then
    export PROTON_LOG=1
    export DXVK_LOG_LEVEL=info
    shift
fi

echo "[proton-launch] Proton:   $PROTON_DIR"
echo "[proton-launch] Prefix:   $PFX_DIR"
echo "[proton-launch] DXVK:     $(cat "$PROTON_DIR/files/lib/wine/dxvk/version" 2>/dev/null || echo 'built-in')"
echo "[proton-launch] Starting AviUtl2..."

exec "$PROTON_DIR/proton" run "$PROJECT_DIR/aviutl2.exe" "$@"
