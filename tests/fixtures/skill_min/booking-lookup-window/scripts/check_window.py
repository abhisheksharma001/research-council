#!/usr/bin/env python3
"""Count lookup-tool attempts inside a UTC window. Usage: check_window.py <export.json> <HH:MM> <HH:MM>"""
import json
import sys


def main(argv):
    calls = json.load(open(argv[1], encoding="utf-8"))
    start, end = argv[2], argv[3]
    inside = [c for c in calls if start <= c["start_utc"] <= end]
    attempts = sum(1 for c in inside for t in c["tool_calls"] if t == "lookup_repair_order")
    if not inside:
        print(f"EMPTY 0 calls in window {start}-{end}")
        return 2
    if attempts == 0:
        print(f"SILENT {len(inside)} calls in window {start}-{end}, 0 lookup attempts")
        return 1
    print(f"OK {len(inside)} calls in window {start}-{end}, {attempts} lookup attempts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
