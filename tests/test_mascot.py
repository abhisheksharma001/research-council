import json
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mascot_gif  # noqa: E402

GIF = ROOT / "assets" / "mascot" / "pup.gif"
JS = ROOT / "assets" / "mascot" / "pup.js"


def gif_frames(data):
    """Walk the GIF block structure; return (width, height, frame_count, loops_forever)."""
    assert data[:6] == b"GIF89a"
    w, h, flags = struct.unpack("<HHB", data[6:11])
    pos = 13
    if flags & 0x80:
        pos += 3 << ((flags & 7) + 1)
    frames, loops = 0, False

    def skip_sub_blocks(p):
        while data[p]:
            p += data[p] + 1
        return p + 1

    while data[pos] != 0x3B:
        if data[pos] == 0x21:
            label = data[pos + 1]
            if label == 0xFF and data[pos + 3:pos + 14] == b"NETSCAPE2.0":
                loops = True
            pos = skip_sub_blocks(pos + 2)
        elif data[pos] == 0x2C:
            frames += 1
            pos += 10
            if data[pos - 1] & 0x80:
                pos += 3 << ((data[pos - 1] & 7) + 1)
            pos = skip_sub_blocks(pos + 1)
        else:
            raise AssertionError(f"unknown block 0x{data[pos]:02x} at {pos}")
    return w, h, frames, loops


class GifOnDisk(unittest.TestCase):
    """S-26: the committed GIF is a real looping GIF89a at 4x with one frame per animation step."""

    def test_gif_is_looping_gif89a_at_4x_with_all_frames(self):
        w, h, frames, loops = gif_frames(GIF.read_bytes())
        self.assertEqual((w, h), (256, 192))
        self.assertTrue(loops)
        self.assertEqual(frames, 122)

    def test_readme_shows_the_gif(self):
        self.assertIn("assets/mascot/pup.gif", (ROOT / "README.md").read_text(encoding="utf-8"))


class Encoder(unittest.TestCase):
    """The LZW stream decodes back to the indices it was given."""

    @staticmethod
    def lzw_decode(data, min_code_size):
        clear, eoi = 1 << min_code_size, (1 << min_code_size) + 1
        width, table = min_code_size + 1, [bytes([i]) for i in range(clear)] + [b"", b""]
        buf = nbits = pos = 0
        out, prev = bytearray(), None
        while True:
            while nbits < width:
                buf |= data[pos] << nbits
                pos += 1
                nbits += 8
            code = buf & ((1 << width) - 1)
            buf >>= width
            nbits -= width
            if code == clear:
                table = table[:eoi + 1]
                width, prev = min_code_size + 1, None
                continue
            if code == eoi:
                return bytes(out)
            entry = table[code] if code < len(table) else prev + prev[:1]
            out += entry
            if prev is not None and len(table) < 4096:
                table.append(prev + entry[:1])
            prev = entry
            if len(table) == (1 << width) and width < 12:
                width += 1

    def test_roundtrip(self):
        rng = random.Random(1)
        src = bytes(rng.randrange(15) for _ in range(40000))   # fills the 4096 table, forces a clear
        enc = mascot_gif.lzw_encode(src, 4)
        self.assertEqual(self.lzw_decode(enc, 4), src)


@unittest.skipUnless(shutil.which("node"), "node is only needed to regenerate the GIF")
class Source(unittest.TestCase):
    """pup.js is deterministic: two dumps are byte-identical, and the GIF on disk is what it draws."""

    def test_frames_are_deterministic_and_gif_is_current(self):
        a = subprocess.run(["node", str(JS), "--frames"], capture_output=True, text=True, check=True).stdout
        b = subprocess.run(["node", str(JS), "--frames"], capture_output=True, text=True, check=True).stdout
        self.assertEqual(a, b)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pup.gif"
            mascot_gif.write_gif(json.loads(a), 4, out)
            self.assertEqual(out.read_bytes(), GIF.read_bytes())


if __name__ == "__main__":
    unittest.main()
