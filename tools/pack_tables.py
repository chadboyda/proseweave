#!/usr/bin/env python3
"""Pack the string-keyed data tables into proseweave's digest-sorted format (build-time only).

    python3 tools/pack_tables.py zipf  ZIPF.tsv.gz            -> data/zipf_en.bin.gz
    python3 tools/pack_tables.py lemma LEMMA.json.gz          -> data/lemma_en.json.gz (exceptions, rules)
                                                                 + data/lemma_index_en.bin.gz (index sets)
    python3 tools/pack_tables.py synonyms SYNONYMS.json.gz    -> data/synonyms_en.bin.gz
    python3 tools/pack_tables.py syllables SYLLABLES.txt.gz   -> data/syllables_en.bin.gz
    python3 tools/pack_tables.py stress STRESS.txt.gz         -> data/stress_en.bin.gz

Inputs are the tables' plain forms: the Zipf TSV that build_zipf_table.py
writes (word, Zipf value to one decimal), the lemmatizer tables extracted from
spaCy (lemma_exc, lemma_index, lemma_rules), and the WordNet synonym table
({"table": {pos: {lemma: [synonyms]}}}). The packed files hold 64-bit digests
of the keys, sorted, so proseweave loads them with no per-entry work
(src/proseweave/packed.py). Output is deterministic.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from proseweave import text as tk  # noqa: E402
from proseweave.packed import TextKeys, write_tables  # noqa: E402

DATA = ROOT / "src" / "proseweave" / "data"


def zipf(src):
    words, tenths = [], []
    with gzip.open(src, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            w, z = line.rstrip("\n").split("\t")
            t = round(float(z) * 10)
            if t / 10 != float(z) or not 0 <= t <= 255:
                raise ValueError(f"{w}: Zipf value {z} is not a tenth in 0-25.5")
            words.append(w)
            tenths.append(t)
    write_tables(DATA / "zipf_en.bin.gz", {"zipf": TextKeys(words, tenths, "B", div=10)},
                 {"what": "word -> Zipf value (tenths)", "source": "tools/build_zipf_table.py"})


def lemma(src):
    t = json.loads(gzip.open(src).read())
    write_tables(DATA / "lemma_index_en.bin.gz", {p: TextKeys(v) for p, v in sorted(t["lemma_index"].items())},
                 {"what": "lemmatizer index: known lemmas per word class"})
    rest = {k: v for k, v in t.items() if k != "lemma_index"}
    with open(DATA / "lemma_en.json.gz", "wb") as f:
        f.write(gzip.compress(json.dumps(rest, sort_keys=True).encode("utf-8"), compresslevel=9, mtime=0))


def synonyms(src):
    t = json.loads(gzip.open(src).read())["table"]
    write_tables(DATA / "synonyms_en.bin.gz",
                 {p: TextKeys(tk.synonym_key(w, x) for w, s in d.items() for x in s) for p, d in sorted(t.items())},
                 {"what": "WordNet 3.0 synonym pairs (lemma NUL synonym)", "source": "Princeton WordNet 3.0 via NLTK"})


def syllables(src):
    """CMUdict syllable counts (the format build_syllables.py writes: a tab and a count,
    then the words with that count) as a word -> count map."""
    words, counts, n = [], [], 0
    for line in gzip.decompress(open(src, "rb").read()).decode("utf-8").splitlines():
        if line.startswith("\t"):
            n = int(line[1:])
        elif line:
            if not 0 <= n <= 255:
                raise ValueError(f"{line}: {n} syllables")
            words.append(line)
            counts.append(n)
    write_tables(DATA / "syllables_en.bin.gz", {"syllables": TextKeys(words, counts, "B")},
                 {"what": "word -> syllable count (CMU Pronouncing Dictionary 0.7a)",
                  "source": "tools/build_syllables.py"})


def stress(src):
    """CMUdict primary-stress masks (the format build_syllables.py writes: a word, a tab
    and the mask, one per line) as a word -> mask map."""
    words, masks = [], []
    for line in gzip.decompress(open(src, "rb").read()).decode("utf-8").splitlines():
        if line:
            w, m = line.split("\t")
            if not 0 < int(m) < 1 << 16:
                raise ValueError(f"{w}: stress mask {m}")
            words.append(w)
            masks.append(int(m))
    write_tables(DATA / "stress_en.bin.gz", {"stress": TextKeys(words, masks, "H")},
                 {"what": "word -> primary-stress mask, bit i = syllable i (CMU Pronouncing Dictionary "
                          "0.7a); words of two or more syllables whose mask is not 1 (first syllable)",
                  "source": "tools/build_syllables.py"})


if __name__ == "__main__":
    {"zipf": zipf, "lemma": lemma, "synonyms": synonyms, "syllables": syllables,
     "stress": stress}[sys.argv[1]](sys.argv[2])
