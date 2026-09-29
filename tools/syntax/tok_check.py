#!/usr/bin/env python3
"""Token boundary agreement between syntax.tokenize and a spaCy dump.

    python3 tok_check.py DUMP.jsonl [max_docs]
"""
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "proseweave"))
sys.path.insert(0, str(ROOT / "src"))
import syntax  # noqa: E402


def spans(toks):
    out, pos = [], 0
    for text, ws in toks:
        out.append((pos, pos + len(text)))
        pos += len(text) + len(ws)
    return out


def main():
    path, lim = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9
    same = total = mine_total = 0
    miss = collections.Counter()
    for k, line in enumerate(open(path)):
        if k >= lim:
            break
        try:
            d = json.loads(line)
        except ValueError:
            break
        ref = [(t[0], t[1]) for t in d["toks"]]
        text = "".join(a + b for a, b in ref)
        mine = [(t.text, t.ws) for t in syntax.tokenize(text)]
        rs, ms = spans(ref), set(spans(mine))
        total += len(rs)
        mine_total += len(ms)
        for (a, b), (t, _) in zip(rs, ref):
            if (a, b) in ms:
                same += 1
            else:
                miss[t] += 1
    print(f"spaCy tokens matched: {same}/{total} = {same / total:.4f}; mine {mine_total}")
    print(miss.most_common(40))


if __name__ == "__main__":
    main()
