#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <aviutl-output.avi> <encoded.mp4> [extra ffmpeg options]"
    echo ""
    echo "Converts a lossless/uncompressed AVI exported from AviUtl2 to an"
    echo "H.264/AAC MP4 using the host ffmpeg. The defaults are tuned for"
    echo "general compatibility; pass extra flags after the output path."
    exit 1
fi

input="$1"
output="$2"
shift 2

if [[ ! -f "$input" ]]; then
    echo "Error: input file not found: $input" >&2
    exit 1
fi

ffmpeg -y -i "$input" \
    -c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow \
    -movflags +faststart \
    -c:a aac -b:a 192k \
    "$@" \
    "$output"

echo "Encoded: $output"
