#!/usr/bin/env python3
"""Build data/syllables_en.bin.gz and data/stress_en.bin.gz (BUILD TIME ONLY; needs NLTK
and its cmudict corpus).

For every word in the CMU Pronouncing Dictionary 0.7a (BSD 2-clause, Carnegie
Mellon University; the copy distributed as NLTK's `cmudict` corpus), the number
of vowel phonemes (phones carrying a stress digit) in its FIRST listed
pronunciation. Written first grouped by count (a line "<TAB><n>" followed by the
words with n syllables, one per line, sorted) to tools/work/syllables_en.txt.gz,
then packed into the form proseweave reads by tools/pack_tables.py.

The stress table holds, from the same first pronunciation, a mask of the
syllables carrying primary stress (bit i = syllable i; secondary stress counts
as unstressed, except in a word listed with no primary stress). Only words of two or more syllables whose mask is not 1 are
kept: a missing word takes stress on its first syllable, the same fallback
proseweave uses for words the dictionary lacks, and monosyllables take their
stress from their word class. Written as "word<TAB>mask" lines to
tools/work/stress_en.txt.gz, then packed.

Also copies the US English hyphenation patterns (hyph_en_US.dic, BSD-style;
Plain TeX hyphen.tex + TUGboat exceptions, converted by László Németh) used for
words the dictionary lacks, gzipped with their licence header kept in
data/LICENSE_syllables.md.

    python tools/build_syllables.py src/proseweave/data PATH_TO_hyph_en_US.dic
    python tools/build_syllables.py src/proseweave/data --stress-only
    (hyph_en_US.dic: e.g. the dictionaries/ directory of a pyphen install, or LibreOffice's
    dictionaries repository; the cmudict corpus: nltk.download("cmudict"))
"""
import gzip, pathlib, sys
from collections import defaultdict
import nltk

out = pathlib.Path(sys.argv[1])
stress_only = sys.argv[2] == "--stress-only"
d = nltk.corpus.cmudict.dict()
work = pathlib.Path(__file__).resolve().parent / "work"
work.mkdir(exist_ok=True)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pack_tables  # noqa: E402

if not stress_only:
    hyph = pathlib.Path(sys.argv[2])
    by_n = defaultdict(list)
    for w, prons in d.items():
        by_n[sum(1 for p in prons[0] if p[-1].isdigit())].append(w)
    lines = []
    for n in sorted(by_n):
        lines.append(f"\t{n}")
        lines.extend(sorted(by_n[n]))
    plain = work / "syllables_en.txt.gz"
    plain.write_bytes(gzip.compress(("\n".join(lines) + "\n").encode("utf-8"), 9, mtime=0))
    pack_tables.syllables(plain)                     # -> data/syllables_en.bin.gz
    (out / "hyph_en_US.dic.gz").write_bytes(gzip.compress(hyph.read_bytes(), 9, mtime=0))

masks = []
for w in sorted(d):
    digits = [p[-1] for p in d[w][0] if p[-1].isdigit()]
    # primary stress; a word listed with secondary stress only takes that
    m = sum(1 << i for i, x in enumerate(digits) if x == "1") or sum(1 << i for i, x in enumerate(digits) if x == "2")
    if len(digits) >= 2 and m not in (0, 1):
        masks.append(f"{w}\t{m}")
plain = work / "stress_en.txt.gz"
plain.write_bytes(gzip.compress(("\n".join(masks) + "\n").encode("utf-8"), 9, mtime=0))
pack_tables.stress(plain)                            # -> data/stress_en.bin.gz
print(len(d), "words;", len(masks), "stress masks;",
      *(f"{f}: {(out / f).stat().st_size} bytes;" for f in ("syllables_en.bin.gz", "stress_en.bin.gz",
                                                               "hyph_en_US.dic.gz")))
