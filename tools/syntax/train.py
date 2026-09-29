#!/usr/bin/env python3
"""Train the tagger, sentence segmenter and parser in syntax.py and write the
weight file. Build-time only; standard library.

    python3 train.py OUT.json.gz DUMP.jsonl [DUMP.jsonl ...] [--epochs N] [--max-tokens N]
           [--gold-ud EWT.conllu]   (train on UD gold trees instead of the dumps)

The dumps are spaCy parses of open-licensed text (see dump_spacy.py). Heads are
learned exactly as they appear there; only the weights leave this script.
"""
import argparse
import collections
import functools
import gzip
import json
import pickle
import pathlib
import random
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "proseweave"))
sys.path.insert(0, str(ROOT / "src"))
import syntax  # noqa: E402
from syntax import (LEFT, RIGHT, SHIFT, Parser, Perceptron, Segmenter, Tagger, Upos, _apply, _norm,  # noqa: E402
                    rule_lemma)


# --------------------------------------------------------------------------
# data

def load_dumps(paths, max_tokens):
    """Documents from each dump, shuffled; PATH:N caps that dump at N tokens."""
    out = []
    for spec in paths:
        p, _, cap = spec.partition(":")
        cap = int(cap) if cap else max_tokens
        docs = []
        for line in open(p):
            try:
                docs.append(json.loads(line))
            except ValueError:          # a dump still being written
                break
        random.Random(7).shuffle(docs)
        n = 0
        for d in docs:
            if n >= cap:
                break
            out.append(d)
            n += len(d["toks"])
    random.Random(8).shuffle(out)
    return out


def sentences(doc):
    """(word indices, heads within the sentence) per spaCy sentence, space tokens left out."""
    toks = doc["toks"]
    sents, cur = [], []
    for i, t in enumerate(toks):
        if t[5] and cur:
            sents.append(cur)
            cur = []
        cur.append(i)
    if cur:
        sents.append(cur)
    out = []
    for s in sents:
        words = [i for i in s if toks[i][0].strip()]
        if not words:
            continue
        pos = {i: k for k, i in enumerate(words)}
        heads = []
        ok = True
        for i in words:
            h = toks[i][4]
            if h == i:
                heads.append(len(words))          # the root
            elif h in pos:
                heads.append(pos[h])
            else:
                ok = False
                break
        if ok and sum(1 for h in heads if h == len(words)) == 1:
            out.append((words, heads))
    return out


def projective(heads):
    n = len(heads)
    arcs = [(min(i, h), max(i, h)) for i, h in enumerate(heads)]
    for a, b in arcs:
        for c, d in arcs:
            if a < c < b < d:
                return False
    return True


def ud_docs(path):
    """UD gold trees as pseudo-dumps (each sentence its own start)."""
    docs, toks = [], []
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("# newdoc") and toks:
            docs.append({"toks": toks})
            toks = []
        if not line or line.startswith("#"):
            if not line and toks:
                toks[-1][1] = " "
            continue
        c = line.split("\t")
        if "-" in c[0] or "." in c[0]:
            continue
        base = len(toks) - (int(c[0]) - 1)
        h = int(c[6])
        toks.append([c[1], "" if "SpaceAfter=No" in c[9] else " ", c[4], c[3],
                     base + h - 1 if h else len(toks), int(c[0] == "1")])
    if toks:
        docs.append({"toks": toks})
    return docs


# --------------------------------------------------------------------------
# tagger

def train_tagger(docs, epochs, seed=1, ahead=None):
    """One tagging pass. With `ahead` ({id(doc): first-pass tags}), the second pass."""
    counts = collections.defaultdict(collections.Counter)
    for d in docs:
        for t in d["toks"]:
            counts[t[0]][t[2]] += 1
    tagdict = {w: c.most_common(1)[0][0] for w, c in counts.items()
               if sum(c.values()) >= 20 and c.most_common(1)[0][1] / sum(c.values()) >= 0.995}
    classes = sorted({t[2] for d in docs for t in d["toks"]})
    cidx = {c: k for k, c in enumerate(classes)}
    model = Perceptron(classes)
    tg = Tagger(model, tagdict)
    rng = random.Random(seed)
    order = list(range(len(docs)))
    for ep in range(epochs):
        rng.shuffle(order)
        right = total = 0
        for k in order:
            toks = docs[k]["toks"]
            words = [t[0] for t in toks]
            ah = ahead[id(docs[k])] if ahead is not None else None
            p1 = p2 = "!START"
            for i, t in enumerate(toks):
                gold = t[2]
                if not words[i].strip() or words[i] in tagdict:
                    guess = tagdict.get(words[i], "_SP")
                else:
                    f = tg.features(words, i, p1, p2, ah)
                    s = model.scores(f)
                    g = max(range(len(s)), key=s.__getitem__)
                    guess = classes[g]
                    model.update(cidx[gold], g, f)
                    right += guess == gold
                    total += 1
                p2, p1 = p1, guess
        print(f"  tagger epoch {ep}: {right / max(total, 1):.4f} (non-dict tokens)", flush=True)
    model.average()
    return tg


# --------------------------------------------------------------------------
# coarse classes and lemma corrections

def upos_rows(doc, tags):
    """(words, tags, heads, kids, gold classes) over the non-space tokens."""
    toks = doc["toks"]
    idx = [i for i, t in enumerate(toks) if t[0].strip()]
    pos_of = {i: k for k, i in enumerate(idx)}
    heads = [pos_of.get(toks[i][4], k) for k, i in enumerate(idx)]
    kids = [[] for _ in idx]
    for k, h in enumerate(heads):
        if h != k:
            kids[h].append(k)
    return ([toks[i][0] for i in idx], [tags[i] for i in idx], heads, kids, [toks[i][3] for i in idx])


def train_upos(rows, epochs, seed=4):
    classes = sorted({g for r in rows for g in r[4]})
    cidx = {c: k for k, c in enumerate(classes)}
    model = Perceptron(classes)
    rng = random.Random(seed)
    for ep in range(epochs):
        rng.shuffle(rows)
        right = total = 0
        for words, tags, heads, kids, gold in rows:
            for i in range(len(words)):
                f = Upos.features(words, tags, heads, kids, i)
                s = model.scores(f)
                g = max(range(len(s)), key=s.__getitem__)
                model.update(cidx[gold[i]], g, f)
                right += g == cidx[gold[i]]
                total += 1
        print(f"  upos epoch {ep}: {right / max(total, 1):.4f}", flush=True)
    model.average()
    return model


def tok_exceptions(docs, min_count=2):
    """Whitespace chunks the rule tokenizer splits differently from the build
    parses, always split the same way there: chunk -> tokens."""
    seen = collections.defaultdict(collections.Counter)
    for d in docs:
        chunk, parts = "", []
        for t in d["toks"] + [["\n", "", None]]:
            if not t[0].strip():                  # a whitespace token ends a chunk
                if chunk:
                    seen[chunk][tuple(parts)] += 1
                chunk, parts = "", []
                continue
            chunk += t[0]
            parts.append(t[0])
            if t[1]:
                seen[chunk][tuple(parts)] += 1
                chunk, parts = "", []
    out = {}
    for chunk, c in seen.items():
        split, k = c.most_common(1)[0]
        if k >= min_count and k == sum(c.values()) and list(split) != syntax._split_word(chunk):
            out[chunk] = list(split)
    return out


def lemma_fixes(docs, min_count=2, min_share=0.9):
    """(word, class, tag) -> lemma wherever the reference lemmas consistently
    differ from the rule lemmatizer (auxiliaries, pronouns, clitics)."""
    seen = collections.defaultdict(collections.Counter)
    wrong = collections.Counter()
    rule = functools.lru_cache(maxsize=None)(rule_lemma)
    for d in docs:
        for t in d["toks"]:
            if len(t) > 6 and t[0].strip():
                key = f"{t[0].lower()}|{t[3]}|{t[2]}"
                seen[key][t[6]] += 1
                # judged on the word as written, so a capitalised name is not "wrong"
                wrong[key] += t[6] != rule(t[0], t[2], t[3])
    out = {}
    for key, c in seen.items():
        lem, k = c.most_common(1)[0]
        n = sum(c.values())
        if n >= min_count and k / n >= min_share and wrong[key] / n >= min_share:
            out[key] = lem
    return out


# --------------------------------------------------------------------------
# segmenter

def seg_rows(doc, tags):
    toks = doc["toks"]
    words = [i for i, t in enumerate(toks) if t[0].strip()]
    seq, gold = [], []
    for k, i in enumerate(words):
        prev = words[k - 1] if k else -1
        gap = "".join(toks[j][0] for j in range(prev + 1, i))
        seq.append((toks[i][0], "n" + str(min(gap.count("\n"), 2)) if gap else
                    ("s" if prev >= 0 and toks[prev][1] else "0")))
        # a sentence spaCy starts on a line-break token starts at the next word
        gold.append(int(any(toks[j][5] for j in range(prev + 1, i + 1))))
    return seq, [tags[i] for i in words], gold


def train_segmenter(rows, epochs, seed=2):
    model = Perceptron([0, 1])
    rng = random.Random(seed)
    for ep in range(epochs):
        rng.shuffle(rows)
        right = total = 0
        for seq, tags, gold in rows:
            for i in range(1, len(seq)):
                f = Segmenter.features(seq, tags, i)
                s = model.scores(f)
                g = int(s[1] > s[0])
                model.update(gold[i], g, f)
                right += g == gold[i]
                total += 1
        print(f"  segmenter epoch {ep}: {right / max(total, 1):.4f}", flush=True)
    model.average()
    return Segmenter(model)


# --------------------------------------------------------------------------
# parser, with the arc-hybrid dynamic oracle

def costs(valid, stack, b, n, gold):
    out = {}
    deps_s0 = None
    if stack:
        s0 = stack[-1]
        deps_s0 = sum(1 for k in range(b, n) if gold[k] == s0)
    for a in valid:
        if a == SHIFT:
            c = sum(1 for k in stack if gold[k] == b)
            c += 1 if gold[b] in stack[:-1] else 0
        elif a == LEFT:
            s0 = stack[-1]
            g = gold[s0]
            c = deps_s0 + (1 if g != b and ((len(stack) > 1 and g == stack[-2]) or g > b) else 0)
        else:
            s0 = stack[-1]
            c = deps_s0 + (1 if gold[s0] >= b else 0)
        out[a] = c
    return out


def train_parser(sents, epochs, explore_from=1, p_explore=0.9, seed=3):
    model = Perceptron([SHIFT, LEFT, RIGHT])
    rng = random.Random(seed)
    for ep in range(epochs):
        rng.shuffle(sents)
        right = total = 0
        t0 = time.time()
        for words, tags, gold in sents:
            n = len(words)
            heads = [-1] * n
            lefts = [[] for _ in range(n)]
            rights = [[] for _ in range(n)]
            stack, b = [], 0
            while stack or b < n:
                v = Parser.valid(stack, b, n)
                f = Parser.features(words, tags, n, stack, b, heads, lefts, rights)
                s = model.scores(f)
                guess = max(v, key=s.__getitem__)
                c = costs(v, stack, b, n, gold)
                zero = [a for a in v if c[a] == 0] or [min(v, key=c.__getitem__)]
                best = max(zero, key=s.__getitem__)
                model.update(best, guess, f)
                if c[guess] == 0 or (ep >= explore_from and rng.random() < p_explore):
                    a = guess
                else:
                    a = best
                b = _apply(a, stack, b, n, heads, lefts, rights)
            right += sum(1 for i in range(n) if heads[i] == gold[i])
            total += n
        print(f"  parser epoch {ep}: train UAS {right / total:.4f} ({time.time() - t0:.0f}s)", flush=True)
    model.average()
    return Parser(model)


# --------------------------------------------------------------------------
# packing

def pack(p, scale, min_abs):
    w = {}
    for f, v in p.w.items():
        flat = []
        for c, x in sorted(v.items()):
            q = int(round(x * scale))
            if abs(q) >= min_abs:
                flat += [c, q]
        if flat:
            w[f] = flat
    return {"classes": p.classes, "w": w}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("dumps", nargs="*")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--tag-epochs", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=3_000_000)
    ap.add_argument("--gold-ud")
    ap.add_argument("--scale", type=int, default=20)
    ap.add_argument("--min-abs", type=int, default=1)
    ap.add_argument("--jackknife", type=int, default=2)
    ap.add_argument("--no-second-pass", action="store_true")
    ap.add_argument("--parser-from", help="take the parser weights from this JSON model instead of training")
    a = ap.parse_args()

    docs = ud_docs(a.gold_ud) if a.gold_ud else load_dumps(a.dumps, a.max_tokens)
    print(len(docs), "docs,", sum(len(d["toks"]) for d in docs), "tokens", flush=True)

    # the cheap tables first, so a mistake in them shows before hours of training
    fixes = lemma_fixes(docs)
    print(len(fixes), "lemma corrections")
    tok_exc = tok_exceptions(docs)
    print(len(tok_exc), "tokenizer exceptions", flush=True)

    t0 = time.time()
    ckpt = pathlib.Path(a.out + ".tagging.pkl")
    if ckpt.exists():
        with open(ckpt, "rb") as fh:
            tagger, tagger2, tag_lists = pickle.load(fh)
        tags_of = {id(d): tl for d, tl in zip(docs, tag_lists)}
        print("tagging restored from", ckpt)
    else:
        # jackknifed first-pass tags: the second pass and every later model
        # learn from realistic tagging errors
        tags_of = {}
        folds = [docs[k::a.jackknife] for k in range(a.jackknife)]
        for k in range(a.jackknife):
            print(f"tagger (fold {k})")
            rest = [d for j, f in enumerate(folds) if j != k for d in f]
            tg = train_tagger(rest, a.tag_epochs)
            for d in folds[k]:
                tags_of[id(d)] = tg.tag([t[0] for t in d["toks"]])
        print("tagger (final, first pass)")
        tagger = train_tagger(docs, a.tag_epochs)
        tagger2 = None
        if not a.no_second_pass:
            print("tagger (final, second pass)")
            tagger2 = train_tagger(docs, a.tag_epochs, seed=5, ahead=tags_of)
        with open(ckpt, "wb") as fh:
            pickle.dump((tagger, tagger2, [tags_of[id(d)] for d in docs]), fh)
    print(f"tagging done {time.time() - t0:.0f}s", flush=True)

    print("segmenter")
    segmenter = train_segmenter([seg_rows(d, tags_of[id(d)]) for d in docs], 4)
    print("coarse classes")
    upos = train_upos([upos_rows(d, tags_of[id(d)]) for d in docs], 3)

    blob = {"scale": a.scale, "tagdict": tagger.tagdict, "lemma_fix": fixes, "tok_exc": tok_exc,
            "tagger": pack(tagger.model, a.scale, a.min_abs),
            "segmenter": pack(segmenter.model, a.scale, a.min_abs),
            "upos": pack(upos, a.scale, a.min_abs)}
    if tagger2 is not None:
        blob["tagger2"] = pack(tagger2.model, a.scale, a.min_abs)

    if a.parser_from:
        with gzip.open(a.parser_from, "rt", encoding="utf-8") as fh:
            blob["parser"] = json.load(fh)["parser"]
    else:
        sents = []
        skipped = 0
        for d in docs:
            tags = tags_of[id(d)]
            for words, gold in sentences(d):
                if len(words) > 150 or not projective(gold):
                    skipped += 1
                    continue
                sents.append(([_norm(d["toks"][i][0]) for i in words], [tags[i] for i in words], gold))
        print(f"parser: {len(sents)} sentences ({skipped} skipped: non-projective or > 150 words)", flush=True)
        blob["parser"] = pack(train_parser(sents, a.epochs).model, a.scale, a.min_abs)

    with gzip.open(a.out, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(blob, fh, separators=(",", ":"))
    print("wrote", a.out, pathlib.Path(a.out).stat().st_size // 1024, "kB;",
          {k: len(v["w"]) for k, v in blob.items() if isinstance(v, dict) and "w" in v}, "features")


if __name__ == "__main__":
    main()
