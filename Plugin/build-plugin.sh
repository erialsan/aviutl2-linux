#!/usr/bin/env bash
# Build UpdateChecker plugin for AviUtl2 using MinGW-w64 cross-compiler
#
# Usage:
#   ./build-plugin.sh                    # Build UpdateChecker.dll/aui2
#   ./build-plugin.sh --install          # Build and copy to Wine prefix
#   ./build-plugin.sh --install-prefix PATH  # Build and copy to specific prefix
#
# Requires: x86_64-w64-mingw32-g++ (MinGW-w64 cross-compiler)
# On Arch:  sudo pacman -S mingw-w64-gcc
# On Debian: sudo apt install g++-mingw-w64-x86-64

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PLUGIN_SRC="$SCRIPT_DIR"
BUILD_DIR="$PLUGIN_SRC/build"
CXX="${CXX:-x86_64-w64-mingw32-g++}"
CXXFLAGS="${CXXFLAGS:--std=gnu++17 -O2 -Wall -DUNICODE -D_UNICODE -DWIN32_LEAN_AND_MEAN}"
LDFLAGS="${LDFLAGS:--shared -Wl,--subsystem,windows -static-libstdc++ -static-libgcc}"
LIBS="${LIBS:--luser32 -lshell32 -lcomctl32 -lgdi32 -lole32 -luuid -lurlmon}"
OUTPUT="${OUTPUT:-UpdateChecker}"

# Parse args
INSTALL=false
INSTALL_PREFIX=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --install) INSTALL=true ;;
        --install-prefix) INSTALL=true; INSTALL_PREFIX="$2"; shift ;;
        --help|-h)
            echo "Usage: $0 [--install] [--install-prefix PATH]"
            echo ""
            echo "Builds UpdateChecker plugin using MinGW-w64 cross-compiler."
            echo "Output: $BUILD_DIR/${OUTPUT}.aui2"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# Check cross-compiler
if ! command -v "$CXX" &>/dev/null; then
    echo "Error: MinGW-w64 cross-compiler not found: $CXX"
    echo ""
    echo "Install on Arch Linux:"
    echo "  sudo pacman -S mingw-w64-gcc"
    echo ""
    echo "Install on Debian/Ubuntu:"
    echo "  sudo apt install g++-mingw-w64-x86-64"
    exit 1
fi

# Build
echo "Building UpdateChecker plugin..."
mkdir -p "$BUILD_DIR"

echo "  CXX:      $CXX"
echo "  CXXFLAGS: $CXXFLAGS"
echo "  Output:   ${OUTPUT}.aui2"

"$CXX" $CXXFLAGS "$PLUGIN_SRC/update_checker.cpp" \
    -o "$BUILD_DIR/${OUTPUT}.dll" \
    $LDFLAGS $LIBS

# Rename .dll → .aui2 (AviUtl2 plugin extension)
mv "$BUILD_DIR/${OUTPUT}.dll" "$BUILD_DIR/${OUTPUT}.aui2"

echo "  Done: $BUILD_DIR/${OUTPUT}.aui2"
ls -lh "$BUILD_DIR/${OUTPUT}.aui2"

# Install to Wine prefix
if [ "$INSTALL" = true ]; then
    if [ -n "$INSTALL_PREFIX" ]; then
        PREFIX_DIR="$INSTALL_PREFIX"
    elif [ -n "${WINEPREFIX:-}" ]; then
        PREFIX_DIR="$WINEPREFIX"
    else
        # Auto-detect from repo
        if [ -d "$REPO_ROOT/pfx-ge/pfx" ]; then
            PREFIX_DIR="$REPO_ROOT/pfx-ge/pfx"
        elif [ -d "$REPO_ROOT/pfx-custom/pfx" ]; then
            PREFIX_DIR="$REPO_ROOT/pfx-custom/pfx"
        else
            echo "Error: Cannot auto-detect Wine prefix. Set WINEPREFIX or use --install-prefix."
            exit 1
        fi
    fi

    # Determine plugin directory (ProgramData/aviutl2/Plugin inside prefix)
    if [ -d "$PREFIX_DIR/drive_c/ProgramData/aviutl2/Plugin" ]; then
        PLUGIN_DST="$PREFIX_DIR/drive_c/ProgramData/aviutl2/Plugin"
    elif [ -d "$PREFIX_DIR/drive_c/users/steamuser/AppData/Roaming/aviutl2/Plugin" ]; then
        PLUGIN_DST="$PREFIX_DIR/drive_c/users/steamuser/AppData/Roaming/aviutl2/Plugin"
    else
        # Create the standard path
        PLUGIN_DST="$PREFIX_DIR/drive_c/ProgramData/aviutl2/Plugin"
        mkdir -p "$PLUGIN_DST"
    fi

    cp "$BUILD_DIR/${OUTPUT}.aui2" "$PLUGIN_DST/"
    echo "  Installed to: $PLUGIN_DST/${OUTPUT}.aui2"
fi
