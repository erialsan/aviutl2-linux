#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f "aviutl2.exe" ]]; then
    echo "[debug] aviutl2.exe not found. Please run ./setup.sh first." >&2
    exit 1
fi

if [[ ! -d "wine-custom" || ! -d "pfx-custom" ]]; then
    echo "[debug] Custom Wine/prefix not found. Please run ./setup.sh first." >&2
    exit 1
fi

export WINEARCH=win64
export WINEPREFIX="$PROJECT_DIR/pfx-custom"
export PATH="$PROJECT_DIR/wine-custom/bin:$PATH"
export WINEDLLOVERRIDES="d3d11,dxgi=b;d3dcompiler_47=n"

# Default debug channels. Reduce output but keep what's needed to diagnose crashes.
# +seh  = exception / backtrace
# +d3d11, +dxgi = graphics pipeline
# +dwrite = text layout / font crashes
# +module = loaded DLLs (helps identifying native vs builtin)
# +tid = thread id prefixes
DEFAULT_DEBUG="+seh,+d3d11,+dxgi,+dwrite,+module,+tid"
export WINEDEBUG="${DEBUG_CHANNELS:-$DEFAULT_DEBUG}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
FULL_LOG="$LOG_DIR/debug-${TIMESTAMP}.log"
ERROR_LOG="$LOG_DIR/debug-${TIMESTAMP}.errors.log"

echo "[debug] Full log:   $FULL_LOG"
echo "[debug] Error log:  $ERROR_LOG"
echo "[debug] Channels:   $WINEDEBUG"

export DISPLAY="${DISPLAY:-:1}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"

# Dismiss the two startup dialogs automatically unless NO_DISMISS is set.
# Set NO_DISMISS=1 when you need to read an error dialog before it is closed.
if [[ "${NO_DISMISS:-0}" == "1" ]]; then
    echo "[debug] NO_DISMISS=1: startup dialogs will NOT be dismissed automatically."
    dismiss_pid=""
else
    python3 "$PROJECT_DIR/tools/dismiss-dialogs.py" --display "$DISPLAY" --count 2 --delay 3 &
    dismiss_pid=$!
fi

# We don't want pipefail/grep failure to abort the run just because no
# errors are emitted at the very end of the stream.
set +o pipefail
"$PROJECT_DIR/wine-custom/bin/wine" "$PROJECT_DIR/aviutl2.exe" "$@" 2>&1 \
    | tee "$FULL_LOG" \
    | grep -E --line-buffered '^[[:xdigit:]]+:(err|warn|fixme):' > "$ERROR_LOG" \
    || true
WINE_EXIT=${PIPESTATUS[0]}

if [[ -n "$dismiss_pid" ]]; then
    wait "$dismiss_pid" 2>/dev/null || true
fi

echo "[debug] AviUtl2 exited with code $WINE_EXIT"
echo "[debug] Error summary:"
grep -cE '^[[:xdigit:]]+:(err|warn|fixme):' "$ERROR_LOG" 2>/dev/null \
    | xargs -I{} echo "         {} interesting lines in $ERROR_LOG"

echo "[debug] Last 80 lines of full log:"
tail -n 80 "$FULL_LOG"
