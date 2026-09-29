#!/usr/bin/env python3
"""Recompute the lemma corrections (train.lemma_fixes) from lemma-bearing dumps.

    python3 relemma.py OUT.json DUMP[:N] ...
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from train import lemma_fixes, load_dumps  # noqa: E402

fixes = lemma_fixes(load_dumps(sys.argv[2:], 3_000_000))
json.dump(fixes, open(sys.argv[1], "w"), indent=0, sort_keys=True)
print(len(fixes), "lemma corrections")
