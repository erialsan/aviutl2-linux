#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CACHE_DIR="$PROJECT_DIR/.cache/l-smash-works"
PLUGIN_DIR="$PROJECT_DIR/pfx-custom/drive_c/ProgramData/aviutl2/Plugin"

# Recommended build for AviUtl / AviUtl ExEdit2 as of 2026-06-28.
# If the release changes, override with:
#   LSMASH_ZIP_URL=https://... ./tools/install-lsmash-works.sh
DEFAULT_URL='https://github.com/Mr-Ojii/L-SMASH-Works-Auto-Builds/releases/download/build-2026-06-28-03-04-08/L-SMASH-Works_r1281_Mr-Ojii_Mr-Ojii.zip'
ZIP_URL="${LSMASH_ZIP_URL:-$DEFAULT_URL}"
ZIP_NAME="$(basename "$ZIP_URL")"
ZIP_PATH="$CACHE_DIR/$ZIP_NAME"

mkdir -p "$CACHE_DIR"

cd "$PROJECT_DIR"

if [[ ! -f "aviutl2.exe" ]]; then
    echo "[install-lsmash] aviutl2.exe not found. Please run ./setup.sh first." >&2
    exit 1
fi

if [[ ! -f "$ZIP_PATH" ]]; then
    echo "[install-lsmash] Downloading $ZIP_NAME"
    curl -L -o "$ZIP_PATH" "$ZIP_URL"
fi

echo "[install-lsmash] Extracting AviUtl2 plugin"
unzip -o "$ZIP_PATH" 'AviUtl2/*' -d "$CACHE_DIR"

mkdir -p "$PLUGIN_DIR"
echo "[install-lsmash] Installing lwinput.aui2"
cp "$CACHE_DIR/AviUtl2/lwinput.aui2" "$PLUGIN_DIR/"

echo "[install-lsmash] Done. Restart AviUtl2 and check 設定→入力プラグインの設定."
