#!/usr/bin/env python3
"""Score whole models on a held-out spaCy dump neither was trained on, on
spaCy's own tokens: fine tag, sentence starts (a start on a line-break token
counts for the next word), attachment with spaCy's sentences given, and, where
the model has them, coarse classes and lemmas.

    python3 eval_heldout.py DUMP.jsonl NAME=SYNTAX_PY:DATA [NAME=...]
"""
import importlib.util
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))   # lemma tables


def load(name, spec):
    src, data = spec.split(":")
    sp = importlib.util.spec_from_file_location("syn_" + name, src)
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    mod.DATA = pathlib.Path(data)
    return mod


def main():
    docs = [json.loads(line) for line in open(sys.argv[1])]
    for spec in sys.argv[2:]:
        name, rest = spec.split("=", 1)
        mod = load(name, rest)
        m = mod.models()
        tagger, seg, parser = m[0], m[1], m[2]
        c = dict(n=0, tag=0, tp=0, fp=0, fn=0, uas=0, uasn=0, pos=0, lem=0, lemn=0)
        for d in docs:
            toks = d["toks"]
            mt = [mod.Token(t[0], t[1]) for t in toks]
            words = [i for i, t in enumerate(toks) if t[0].strip()]
            gold, pending = [], False
            for i, t in enumerate(toks):
                if not t[0].strip():
                    pending = pending or bool(t[5])
                    continue
                gold.append(bool(t[5]) or pending)
                pending = False
            # our segmentation
            mod.annotate(mt, tagger, seg, parser)
            for k, i in enumerate(words):
                c["n"] += 1
                c["tag"] += mt[i].tag == toks[i][2]
                if k:
                    g, p = gold[k], mt[i].sent_start
                    c["tp"] += g and p
                    c["fp"] += p and not g
                    c["fn"] += g and not p
            # spaCy's sentences given, for attachment
            mt2 = [mod.Token(t[0], t[1]) for t in toks]
            mod.annotate(mt2, tagger, seg, parser, starts=[k == 0 or gold[k] for k in range(len(words))])
            for i in words:
                h = toks[i][4]
                if toks[h][0].strip():
                    c["uasn"] += 1
                    c["uas"] += mt2[i].head == h
            if hasattr(mod, "annotate_text") and getattr(m, "upos", None) is not None:
                idx = words
                pos_of = {i: k for k, i in enumerate(idx)}
                ws = [mt2[i].text for i in idx]
                tg = [mt2[i].tag for i in idx]
                hd = [pos_of.get(mt2[i].head, k) for k, i in enumerate(idx)]
                kids = [[] for _ in idx]
                for k, h in enumerate(hd):
                    if h != k:
                        kids[h].append(k)
                for k, i in enumerate(idx):
                    s = m.upos.scores(mod.Upos.features(ws, tg, hd, kids, k))
                    p = m.upos.classes[max(range(len(s)), key=s.__getitem__)]
                    c["pos"] += p == toks[i][3]
                    if len(toks[i]) > 6 and any(ch.isalpha() for ch in toks[i][0]):
                        c["lemn"] += 1
                        c["lem"] += mod.lemma(ws[k], tg[k], p, m.lemma_fix) == toks[i][6]
        f1 = 2 * c["tp"] / max(2 * c["tp"] + c["fp"] + c["fn"], 1)
        print(f"{name:<10} tag {c['tag'] / c['n']:.4f}  sent_F1 {f1:.4f}  UAS {c['uas'] / c['uasn']:.4f}"
              + (f"  upos {c['pos'] / c['n']:.4f}" if c["pos"] else "")
              + (f"  lemma {c['lem'] / c['lemn']:.4f}" if c["lemn"] else ""), flush=True)


if __name__ == "__main__":
    main()
