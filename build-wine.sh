#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

export PATH="$HOME/local/usr/bin:$PATH"

# Use ccache if available. This makes repeated rebuilds much faster because
# object files are cached across clean source extractions.
if command -v ccache >/dev/null 2>&1; then
    echo "[build-wine] ccache found"
    export CC="ccache gcc"
    export CXX="ccache g++"
    # Grow ccache size so Wine's large object set stays warm across builds.
    ccache -M 20G >/dev/null 2>&1 || true
    ccache -z >/dev/null 2>&1 || true
else
    echo "[build-wine] ccache not found; repeated clean builds will be slow"
    echo "[build-wine] Install with: sudo pacman -S ccache"
fi

WINE_VERSION="11.12"
WINE_TARBALL="wine-${WINE_VERSION}.tar.xz"
WINE_URL="https://dl.winehq.org/wine/source/11.x/${WINE_TARBALL}"
SOURCE_DIR="$PROJECT_DIR/wine-src"
INSTALL_PREFIX="$PROJECT_DIR/wine-custom"
CACHE_DIR="$PROJECT_DIR/.cache"
PATCH_DIR="$PROJECT_DIR/patches"

mkdir -p "$CACHE_DIR"

# ------------------------------------------------------------------
# Download source
# ------------------------------------------------------------------
if [[ ! -f "$CACHE_DIR/$WINE_TARBALL" ]]; then
    echo "[build-wine] Downloading Wine ${WINE_VERSION} source"
    curl -L -o "$CACHE_DIR/$WINE_TARBALL" "$WINE_URL"
fi

# ------------------------------------------------------------------
# Detect patch set changes via hash. Only re-extract + re-patch the source
# tree when the tarball content OR the set of *.patch files has changed.
# This makes incremental rebuilds skip the ~30s extract/patch step and,
# more importantly, preserves the in-tree build artifacts (object files)
# so `make` only recompiles what actually changed.
# ------------------------------------------------------------------
PATCH_HASH_FILE="$CACHE_DIR/.patch-hash"
NEW_PATCH_HASH=$(cat "$CACHE_DIR/$WINE_TARBALL" "$PATCH_DIR"/*.patch 2>/dev/null | sha256sum | awk '{print $1}')
OLD_PATCH_HASH=""
[[ -f "$PATCH_HASH_FILE" ]] && OLD_PATCH_HASH=$(cat "$PATCH_HASH_FILE")

NEED_REEXTRACT=0
if [[ "$NEW_PATCH_HASH" != "$OLD_PATCH_HASH" ]]; then
    NEED_REEXTRACT=1
elif [[ ! -d "$SOURCE_DIR" ]] || [[ ! -f "$SOURCE_DIR/configure" ]]; then
    NEED_REEXTRACT=1
fi

if [[ $NEED_REEXTRACT -eq 1 ]]; then
    echo "[build-wine] Patch set changed or source missing — re-extracting and re-patching"
    rm -rf "$SOURCE_DIR"
    mkdir -p "$SOURCE_DIR"
    tar -xf "$CACHE_DIR/$WINE_TARBALL" -C "$SOURCE_DIR" --strip-components=1

    if [[ -d "$PATCH_DIR" ]]; then
        for p in "$PATCH_DIR"/*.patch; do
            [[ -f "$p" ]] || continue
            echo "[build-wine] Applying $(basename "$p")"
            patch -d "$SOURCE_DIR" -p1 < "$p"
        done
    fi

    echo "$NEW_PATCH_HASH" > "$PATCH_HASH_FILE"
else
    echo "[build-wine] Source tree and patches unchanged — incremental build"
fi

# ------------------------------------------------------------------
# Configure and build
# Build with WoW64 (x86_64 + i386) so that 32-bit helper executables
# and installers used by output plugins (x264guiEx pipe32auo.exe etc.)
# can run in the same prefix as the 64-bit AviUtl2 executable.
# ------------------------------------------------------------------
cd "$SOURCE_DIR"

# Only run ./configure if config.status is missing or configure flags
# / source changed. Re-running configure invalidates all objects.
NEED_CONFIGURE=0
if [[ ! -f config.status ]]; then
    NEED_CONFIGURE=1
fi

if [[ $NEED_CONFIGURE -eq 1 ]]; then
    echo "[build-wine] Configuring (prefix=$INSTALL_PREFIX, archs=x86_64,i386)"
    ./configure \
        --prefix="$INSTALL_PREFIX" \
        --enable-archs=x86_64,i386 \
        --disable-tests \
        --without-opencl \
        --without-wayland \
        --without-capi \
        --without-oss \
        --without-gphoto \
        --without-sane \
        --without-v4l2 \
        --without-cups \
        --without-krb5 \
        --without-netapi \
        --without-usb
else
    echo "[build-wine] config.status present — skipping configure"
fi

# Use more parallelism. i5-1235U has 10 logical cores; -j8 is a safe
# ceiling that leaves headroom for the linker. Override with MAX_JOBS.
MAX_JOBS="${MAX_JOBS:-8}"
echo "[build-wine] Building with -j$MAX_JOBS (ccache warm if patches unchanged)"
make -j"$MAX_JOBS"

echo "[build-wine] Installing"
make install

if command -v ccache >/dev/null 2>&1; then
    echo "[build-wine] ccache stats:"
    ccache -s 2>/dev/null | grep -E 'cache hit|cache miss|cache size' || true
fi

echo "[build-wine] Done. Wine is installed in $INSTALL_PREFIX."
