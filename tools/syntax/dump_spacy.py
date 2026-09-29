#!/usr/bin/env python3
"""Parse raw text with spaCy en_core_web_sm (MIT) and write the annotations the
parser is distilled from. Build-time only; run with a python that has spaCy.

    python dump_spacy.py OUT.jsonl DIR [DIR ...]

One JSON line per document: {"id", "toks": [[text, ws, tag, pos, head, sent_start, lemma, dep], ...]}
where head is the document-level token index and ws is the trailing whitespace.
"""
import json
import pathlib
import sys

import spacy

nlp = spacy.load("en_core_web_sm", disable=["ner"])
nlp.max_length = 3_000_000
out = open(sys.argv[1], "w")
paths = sorted(p for d in sys.argv[2:] for p in pathlib.Path(d).glob("*.txt"))


def chunks(text, size=40000):
    """Long books are cut at paragraph breaks so each piece looks like one article."""
    cur, n = [], 0
    for p in text.split("\n\n"):
        cur.append(p)
        n += len(p)
        if n >= size:
            yield "\n\n".join(cur)
            cur, n = [], 0
    if cur:
        yield "\n\n".join(cur)


texts = [(f"{p.parent.name}/{p.stem}/{k}", c) for p in paths
         for k, c in enumerate(chunks(p.read_text(encoding="utf-8")))]
for (i, _), doc in zip(texts, nlp.pipe((t for _, t in texts), batch_size=16)):
    toks = [[t.text, t.whitespace_, t.tag_, t.pos_, t.head.i, int(t.is_sent_start or t.i == 0), t.lemma_, t.dep_] for t in doc]
    out.write(json.dumps({"id": i, "toks": toks}) + "\n")
print(len(texts), "docs")
