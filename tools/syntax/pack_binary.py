#!/usr/bin/env python3
"""Convert a JSON weight file (train.py / repack.py output) to the compact
binary file syntax.py loads.

    python3 pack_binary.py IN.json.gz OUT.bin.gz

Layout (gzip): b"PWSYN5", u32 header length, JSON header (model order and
class lists, the tag dictionary, the lemma corrections), then per model:
sorted 32-bit feature keys (uint32, see syntax.feature_key), row lengths
(uint8), class codes (uint8) and weights (int16), all little-endian. Row i
holds the (class, weight) pairs of key i. Features whose keys collide are
merged by summing their weights.
"""
import array
import gzip
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "proseweave"))
sys.path.insert(0, str(ROOT / "src"))
from syntax import feature_key  # noqa: E402

MODELS = ("tagger", "tagger2", "segmenter", "parser", "upos")


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with gzip.open(src, "rt", encoding="utf-8") as fh:
        d = json.load(fh)
    order = [m for m in MODELS if m in d]
    header = {"order": order, "tagdict": d.get("tagdict", {}), "lemma_fix": d.get("lemma_fix", {}),
              "tok_exc": d.get("tok_exc", {}), "seg_features": d.get("seg_features", "full"),
              "models": {}}
    parts = []
    for m in order:
        rows = {}
        for f, v in d[m]["w"].items():
            r = rows.setdefault(feature_key(f), {})
            for k in range(0, len(v), 2):
                r[v[k]] = r.get(v[k], 0) + v[k + 1]
        keys = array.array("I", sorted(rows))
        lens, cls, w = array.array("B"), array.array("B"), array.array("h")
        for key in keys:
            for c, x in sorted(rows[key].items()):
                cls.append(c)
                w.append(max(-32768, min(32767, x)))
            lens.append(len(rows[key]))
        if sys.byteorder == "big":
            for a in (keys, w):
                a.byteswap()
        bufs = [keys.tobytes(), lens.tobytes(), cls.tobytes(), w.tobytes()]
        header["models"][m] = {"classes": d[m]["classes"], "sizes": [len(b) for b in bufs],
                               "collisions": len(d[m]["w"]) - len(keys)}
        parts += bufs
    h = json.dumps(header, separators=(",", ":")).encode("utf-8")
    with gzip.open(dst, "wb", compresslevel=9) as fh:
        fh.write(b"PWSYN5" + struct.pack("<I", len(h)) + h)
        for b in parts:
            fh.write(b)
    print(dst, pathlib.Path(dst).stat().st_size // 1024, "kB;",
          {m: (len(d[m]["w"]), header["models"][m]["collisions"]) for m in order}, "(features, collisions)")


if __name__ == "__main__":
    main()
