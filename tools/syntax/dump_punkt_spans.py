#!/usr/bin/env python3
"""NLTK punkt sentence start offsets per file (measurement only).

    python dump_punkt_spans.py CORPUS_DIR OUT.json
"""
import json
import pathlib
import sys

from nltk.tokenize import sent_tokenize

out = {}
for p in sorted(pathlib.Path(sys.argv[1]).glob("*.txt")):
    text = p.read_text(encoding="utf-8")
    starts, pos = [], 0
    for s in sent_tokenize(text):
        k = text.find(s, pos)
        if k < 0:
            k = text.find(s[:20], pos)
        if k >= 0:
            starts.append(k)
            pos = k + len(s)
    out[p.name] = starts
json.dump(out, open(sys.argv[2], "w"))
print(len(out))
