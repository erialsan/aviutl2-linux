#!/usr/bin/env python3
"""Summarize a Wine debug error log by collapsing repeated messages.

Usage:
    python3 tools/summarize-errors.py logs/debug-YYYYMMDD_HHMMSS.errors.log
"""

import argparse
import re
import sys
from collections import Counter


def normalize(line: str) -> str:
    # Drop thread prefix and the leading channel tag remains.
    # Example: "0160:err:d3d:wined3d_swapchain_resize_buffers Something..."
    line = re.sub(r"^[0-9a-f]+:", "", line)
    # Normalize pointer / handle addresses, object ids and random hex.
    line = re.sub(r"\b0x[0-9a-fA-F]+\b", "0x...", line)
    line = re.sub(r"\b[0-9a-fA-F]{8,}\b", "...", line)
    # Normalize small integer arguments that often vary (e.g. format 87).
    line = re.sub(r"\bformat \d+", "format N", line)
    return line.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Wine debug error log")
    parser.add_argument("log", help="Path to the .errors.log file")
    parser.add_argument("-n", "--top", type=int, default=50,
                        help="Number of top messages to show")
    args = parser.parse_args()

    try:
        with open(args.log, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"File not found: {args.log}", file=sys.stderr)
        sys.exit(1)

    counts = Counter(normalize(line) for line in lines if line.strip())
    total = len(lines)

    print(f"Total lines: {total}")
    print(f"Unique messages: {len(counts)}")
    print()

    for msg, count in counts.most_common(args.top):
        print(f"{count:5d}  {msg}")


if __name__ == "__main__":
    main()
