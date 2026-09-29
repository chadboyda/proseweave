#!/usr/bin/env python3
"""Shrink a weight file: drop weights below a threshold (in stored units),
per model, and optionally splice in a separately trained segmenter.

    python3 repack.py IN.json.gz OUT.json.gz parser=40,tagger=24,tagger2=24,upos=30,segmenter=1
                      [--segmenter SEG.json] [--lemma-fix FIXES.json]

A model not named keeps every weight. --segmenter takes train_seg2.py's
output (its weights and feature-set name replace the input's). --lemma-min
drops lemma corrections seen fewer than N times (needs train.py's counts;
without them it is ignored).
"""
import argparse
import gzip
import json
import pathlib


def prune(block, k):
    w = {}
    for f, v in block["w"].items():
        flat = []
        for i in range(0, len(v), 2):
            if abs(v[i + 1]) >= k:
                flat += [v[i], v[i + 1]]
        if flat:
            w[f] = flat
    return {"classes": block["classes"], "w": w}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("thresholds")
    ap.add_argument("--segmenter")
    ap.add_argument("--lemma-fix", help="replace the lemma corrections with this JSON (relemma.py)")
    a = ap.parse_args()
    th = {k: int(v) for k, v in (x.split("=") for x in a.thresholds.split(","))}
    with gzip.open(a.src, "rt", encoding="utf-8") as fh:
        d = json.load(fh)
    if a.segmenter:
        s = json.load(open(a.segmenter))
        d["segmenter"] = s["segmenter"]
        d["seg_features"] = s["seg_features"]
    if a.lemma_fix:
        d["lemma_fix"] = json.load(open(a.lemma_fix))
    for m in [m for m, v in d.items() if isinstance(v, dict) and "w" in v]:
        if m in th:
            d[m] = prune(d[m], th[m])
    with gzip.open(a.dst, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(d, fh, separators=(",", ":"))
    print(a.dst, pathlib.Path(a.dst).stat().st_size // 1024, "kB",
          {b: len(v["w"]) for b, v in d.items() if isinstance(v, dict) and "w" in v})


if __name__ == "__main__":
    main()
