#!/usr/bin/env python3
"""Score proseweave's values against reference values, per property.

    python3 score.py my_reference.json open/proseweave.json
    python3 score.py my_reference.json articles/proseweave.json --json

Both files map text id -> {property: value}. Reference outputs are not
redistributed: generate your own by running the reference tools on the corpus
texts (open/texts; the articles rebuild with articles/rebuild.py) and save
them as my_reference.json. The pass mark was fixed before
validation (PROTOCOL.md): Spearman rho >= 0.80 and a bootstrap 90% lower bound
>= 0.70. A reference with fewer than 8 distinct values is reported as flat and
not scored. Standard library only.
"""
from __future__ import annotations

import json
import random
import statistics
import sys

RHO_PASS, LOWER_PASS = 0.80, 0.70


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(a, b):
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 0.0


def spearman(a, b):
    return pearson(ranks(a), ranks(b))


def bootstrap_lower(a, b, n=400, q=0.05, seed=11):
    rng = random.Random(seed)
    idx = list(range(len(a)))
    vals = sorted(spearman([a[i] for i in s], [b[i] for i in s])
                  for s in ([rng.choice(idx) for _ in idx] for _ in range(n)))
    return vals[int(q * n)]


def score(pred: dict, ref: dict) -> dict:
    props = sorted({p for row in pred.values() for p in row})
    out = {}
    for p in props:
        ids = [t for t in pred if isinstance(pred[t].get(p), (int, float))
               and isinstance(ref.get(t, {}).get(p), (int, float))]
        a, b = [float(pred[t][p]) for t in ids], [float(ref[t][p]) for t in ids]
        if len(ids) < 10:
            out[p] = {"n": len(ids), "status": "no reference"}
        elif len(set(round(x, 9) for x in b)) < 8:
            out[p] = {"n": len(ids), "status": "flat reference"}
        else:
            rho, lo = spearman(a, b), bootstrap_lower(a, b)
            out[p] = {"n": len(ids), "rho": round(rho, 3), "lower90": round(lo, 3),
                      "status": "pass" if rho >= RHO_PASS and lo >= LOWER_PASS else "below bar"}
    return out


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if len(a) < 2:
        print(__doc__)
        return 2
    res = score(json.load(open(a[1])), json.load(open(a[0])))
    if "--json" in a:
        print(json.dumps(res, indent=1))
        return 0
    for p, r in res.items():
        print(f"{p:<46} " + (f"rho {r['rho']:.2f}  lower90 {r['lower90']:.2f}  {r['status']}"
                             if "rho" in r else r["status"]))
    scored = [r for r in res.values() if "rho" in r]
    print(f"{sum(r['status'] == 'pass' for r in scored)} of {len(res)} pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
