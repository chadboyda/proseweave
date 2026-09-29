#!/usr/bin/env python3
"""Rebuild UD EWT dev and test raw text into documents (never used in
training), for a held-out comparison of models trained on different dumps.

    python3 ewt_heldout_text.py OUT_DIR
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parents[2] / "build" / "syntax"
out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
n = 0
for split in ("dev", "test"):
    docs, cur, par = [], [], []
    for line in open(HERE / "data" / f"en_ewt-ud-{split}.conllu", encoding="utf-8"):
        if line.startswith("# newdoc"):
            if par:
                cur.append(" ".join(par))
            if cur:
                docs.append("\n\n".join(cur))
            cur, par = [], []
        elif line.startswith("# newpar"):
            if par:
                cur.append(" ".join(par))
            par = []
        elif line.startswith("# text = "):
            par.append(line[9:].strip())
    if par:
        cur.append(" ".join(par))
    if cur:
        docs.append("\n\n".join(cur))
    for t in docs:
        (out / f"{split}_{n:04d}.txt").write_text(t, encoding="utf-8")
        n += 1
print(n, "documents")
