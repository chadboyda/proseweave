#!/usr/bin/env python3
"""Reference annotations for measuring agreement (never for training).

    python dump_corpus.py CORPUS_DIR OUT.json

Per file: spaCy en_core_web_sm tokens [text, ws, tag, pos, lemma, head, sent_start, dep]
over the whole text, and the NLTK punkt sentence count (used to measure sentence-count agreement).
"""
import json
import pathlib
import sys

import spacy
from nltk.tokenize import sent_tokenize

nlp = spacy.load("en_core_web_sm")
out = {}
for p in sorted(pathlib.Path(sys.argv[1]).glob("*.txt")):
    text = p.read_text(encoding="utf-8")
    doc = nlp(text)
    out[p.name] = {
        "toks": [[t.text, t.whitespace_, t.tag_, t.pos_, t.lemma_, t.head.i, int(t.is_sent_start or t.i == 0), t.dep_]
                 for t in doc],
        "punkt": len(sent_tokenize(text)),
    }
json.dump(out, open(sys.argv[2], "w"))
print(len(out), "files")
