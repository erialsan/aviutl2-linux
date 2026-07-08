#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [[ "${1:-}" == "--debug" ]]; then
    shift
    exec "$PROJECT_DIR/debug.sh" "$@"
fi

if [[ ! -f "aviutl2.exe" ]]; then
    echo "[launch] aviutl2.exe not found. Please run ./setup.sh first." >&2
    exit 1
fi

if [[ ! -d "wine-custom" || ! -d "pfx-custom" ]]; then
    echo "[launch] Custom Wine/prefix not found. Please run ./setup.sh first." >&2
    exit 1
fi

export WINEARCH=win64
export WINEPREFIX="$PROJECT_DIR/pfx-custom"
export PATH="$PROJECT_DIR/wine-custom/bin:$PATH"

# Use Wine's built-in d3d11/dxgi (WineD3D). DXVK has additional unimplemented
# DXGI internals, so WineD3D is the current working path.
# d3dcompiler_47 is the native Microsoft DLL installed by setup.sh.
export WINEDLLOVERRIDES="d3d11,dxgi=b;d3dcompiler_47=n"

# Optional: force software OpenGL rendering to rule out GPU driver issues.
# Set AVIUTL2_SOFTWARE_RENDER=1 before launch.sh to enable llvmpipe.
if [[ "${AVIUTL2_SOFTWARE_RENDER:-0}" == "1" ]]; then
    export LIBGL_ALWAYS_SOFTWARE=1
fi

# Make sure the display environment is available to child processes.
export DISPLAY="${DISPLAY:-:1}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"

exec "$PROJECT_DIR/wine-custom/bin/wine" "$PROJECT_DIR/aviutl2.exe" "$@"
