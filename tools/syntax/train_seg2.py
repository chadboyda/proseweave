#!/usr/bin/env python3
"""Retrain the sentence segmenter with extra annotated text, using the tagger
from a train.py checkpoint, and choose the feature set on held-out documents.

    python3 train_seg2.py CKPT.tagging.pkl OUT.json MAIN_DUMP[:N] ... --extra DUMP ... [--features base,full]

MAIN dumps must be given exactly as they were to train.py (their jackknifed
tags come from the checkpoint); EXTRA dumps are tagged with the final
two-pass tagger. Every 20th document of the combined, shuffled list is held
out; F1 against spaCy's sentence starts (a start on a line-break token counts
for the next word) chooses the feature set. The winner is retrained on all
documents and written, packed, to OUT.json as {"segmenter": ..., "report": ...}.
"""
import argparse
import importlib.util
import json
import pathlib
import pickle
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "proseweave"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
import syntax  # noqa: E402
from train import load_dumps, pack, seg_rows  # noqa: E402


FEATURES = {"base": syntax.Segmenter.features_base, "full": syntax.Segmenter.features}


def train(rows, feats, epochs, seed=2):
    model = syntax.Perceptron([0, 1])
    rng = random.Random(seed)
    rows = list(rows)
    for ep in range(epochs):
        rng.shuffle(rows)
        for seq, tags, gold in rows:
            for i in range(1, len(seq)):
                f = feats(seq, tags, i)
                s = model.scores(f)
                model.update(gold[i], int(s[1] > s[0]), f)
        print(f"    epoch {ep}", flush=True)
    model.average()
    return model


def f1(model, rows, feats):
    tp = fp = fn = 0
    for seq, tags, gold in rows:
        for i in range(1, len(seq)):
            s = model.scores(feats(seq, tags, i))
            g = int(s[1] > s[0])
            tp += g and gold[i]
            fp += g and not gold[i]
            fn += (not g) and gold[i]
    p, r = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    return round(p, 4), round(r, 4), round(2 * p * r / max(p + r, 1e-9), 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt")
    ap.add_argument("out")
    ap.add_argument("dumps", nargs="+")
    ap.add_argument("--extra", nargs="*", default=[])
    ap.add_argument("--features", default="base,full")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=3_000_000)
    ap.add_argument("--scale", type=int, default=20)
    ap.add_argument("--compare", nargs="*", default=[], help="SYNTAX_PY:DATA of another model to score")
    a = ap.parse_args()

    with open(a.ckpt, "rb") as fh:
        tagger, tagger2, tag_lists = pickle.load(fh)
    two = syntax.Tagger(tagger.model, tagger.tagdict, tagger2.model if tagger2 else None)
    docs = load_dumps(a.dumps, a.max_tokens)
    assert len(docs) == len(tag_lists), "main dumps must match the checkpoint's"
    rows = [seg_rows(d, tl) for d, tl in zip(docs, tag_lists)]
    extra = load_dumps(a.extra, a.max_tokens) if a.extra else []
    for d in extra:
        rows.append(seg_rows(d, two.tag([t[0] for t in d["toks"]])))
    all_docs = docs + extra
    print(len(rows), "documents", flush=True)
    order = list(range(len(rows)))
    random.Random(3).shuffle(order)
    rows = [rows[k] for k in order]
    held, fit = rows[::20], [r for k, r in enumerate(rows) if k % 20]
    held_docs = [all_docs[k] for k in order[::20]]

    report = {}
    for spec in a.compare:
        # another shipped model, with its own tagger, on the same held-out documents
        src, data = spec.split(":")
        sp = importlib.util.spec_from_file_location(f"syntax_cmp{len(report)}", src)
        mod = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(mod)
        mod.DATA = pathlib.Path(data)
        tg, sg = mod.models()[0], mod.models()[1]
        crow = [seg_rows(d, tg.tag([t[0] for t in d["toks"]])) for d in held_docs]
        feats = getattr(sg, "feats", None) or mod.Segmenter.features
        report["compare:" + data] = f1(sg.model, crow, feats)
        print("  compare", data, report["compare:" + data], flush=True)
    for name in a.features.split(","):
        print("features", name, flush=True)
        m = train(fit, FEATURES[name], a.epochs)
        report[name] = f1(m, held, FEATURES[name])
        print("  held-out (P, R, F1)", report[name], flush=True)
    best = max((k for k in report if not k.startswith("compare:")), key=lambda k: report[k][2])
    print("chosen:", best, "- retraining on every document", flush=True)
    m = train(rows, FEATURES[best], a.epochs)
    json.dump({"seg_features": best, "report": report, "segmenter": pack(m, a.scale, 1)}, open(a.out, "w"))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
