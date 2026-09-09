#!/usr/bin/env python3
"""Write assets/mascot/pup.gif from assets/mascot/pup.js.

Usage:
  python3 scripts/mascot_gif.py [--scale 4] [--out assets/mascot/pup.gif]

Runs `node assets/mascot/pup.js --frames` (node is a dev-only tool; the GIF is committed so
nobody needs it to use the plugin), then encodes the frames as a looping GIF89a with the
standard library only. One global palette, one LZW stream per frame, frame delay from the
JS STEP_MS. Exit 0 on success, 1 when node is missing or the frame dump is malformed.
"""
import argparse
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "assets" / "mascot" / "pup.js"


def frames_from_node():
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node not found on PATH; needed only to regenerate the GIF")
    out = subprocess.run([node, str(JS), "--frames"], capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    for key in ("w", "h", "step_ms", "palette", "frames"):
        if key not in data:
            raise RuntimeError(f"frame dump missing {key}")
    return data


def lzw_encode(indices, min_code_size):
    """Standard GIF LZW: emit codes into a byte string, variable code width, clear at 4096."""
    clear, eoi = 1 << min_code_size, (1 << min_code_size) + 1
    table = {bytes([i]): i for i in range(clear)}
    next_code, width = eoi + 1, min_code_size + 1
    out, buf, nbits = bytearray(), 0, 0

    def emit(code):
        nonlocal buf, nbits, width
        buf |= code << nbits
        nbits += width
        while nbits >= 8:
            out.append(buf & 0xFF)
            buf >>= 8
            nbits -= 8

    emit(clear)
    cur = b""
    for i in indices:
        nxt = cur + bytes([i])
        if nxt in table:
            cur = nxt
            continue
        emit(table[cur])
        if next_code < 4096:
            table[nxt] = next_code
            next_code += 1
            if next_code > (1 << width) and width < 12:
                width += 1
        else:
            emit(clear)
            table = {bytes([k]): k for k in range(clear)}
            next_code, width = eoi + 1, min_code_size + 1
        cur = bytes([i])
    if cur:
        emit(table[cur])
    emit(eoi)
    if nbits:
        out.append(buf & 0xFF)
    return bytes(out)


def sub_blocks(data):
    out = bytearray()
    for i in range(0, len(data), 255):
        chunk = data[i:i + 255]
        out.append(len(chunk))
        out += chunk
    out.append(0)
    return bytes(out)


def scale_frame(rows, scale):
    idx = bytearray()
    for row in rows:
        line = bytearray()
        for v in row.split(","):
            line += bytes([int(v)]) * scale
        for _ in range(scale):
            idx += line
    return idx


def write_gif(data, scale, out_path):
    w, h = data["w"] * scale, data["h"] * scale
    palette = data["palette"]
    bits = max(1, (len(palette) - 1).bit_length())
    table = bytearray()
    for hexcol in palette:
        table += bytes.fromhex(hexcol.lstrip("#"))
    table += b"\x00" * ((3 << bits) - len(table))
    delay = max(2, round(data["step_ms"] / 10))
    gif = bytearray(b"GIF89a")
    gif += struct.pack("<HHBBB", w, h, 0x80 | ((bits - 1) << 4) | (bits - 1), 0, 0)
    gif += table
    gif += b"\x21\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00"       # loop forever
    min_code = max(2, bits)
    for fr in data["frames"]:
        if len(fr["rows"]) != data["h"]:
            raise RuntimeError("frame has wrong row count")
        gif += b"\x21\xF9\x04" + struct.pack("<BHB", 0x00, delay, 0) + b"\x00"
        gif += b"\x2C" + struct.pack("<HHHHB", 0, 0, w, h, 0)
        gif += bytes([min_code]) + sub_blocks(lzw_encode(scale_frame(fr["rows"], scale), min_code))
    gif += b"\x3B"
    out_path.write_bytes(bytes(gif))
    return len(data["frames"]), len(gif)


def main(argv):
    p = argparse.ArgumentParser(prog="mascot_gif.py")
    p.add_argument("--scale", type=int, default=4)
    p.add_argument("--out", default=str(ROOT / "assets" / "mascot" / "pup.gif"))
    args = p.parse_args(argv[1:])
    try:
        data = frames_from_node()
        n, size = write_gif(data, args.scale, Path(args.out))
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"{args.out}: {n} frames, {size} bytes, {data['w'] * args.scale}x{data['h'] * args.scale}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
