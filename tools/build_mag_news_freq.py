#!/usr/bin/env python3
"""Build proseweave's news-and-magazine reference frequency tables (the keyness baseline).

BUILD TIME ONLY. The output, mag_news_freq.bin.xz, is read by proseweave/magnews.py
with the standard library. Nothing here runs when proseweave runs.

Corpus (every input open-licensed; see LICENSE_mag_news_freq.md):
  news      Common Pile v0.1 `news_filtered` (common-pile/news_filtered), the
            articles published under CC BY 4.0 (CC BY-SA articles are skipped)
  wikinews  English Wikinews, 2023-07-28 snapshot (izumi-lab/wikinews-en-20230728), CC BY 2.5
  foodista  Common Pile v0.1 `foodista_filtered` (Foodista food writing), CC BY 3.0
  gutenberg Common Pile v0.1 `project_gutenberg_filtered`, first shard, public domain,
            a 10M-word sample (narrative vocabulary that news sites lack)

Pipeline: the one proseweave.source compares texts with, so every key is spelled
and split the way a text's lists are:
  1. Paragraphs, exact duplicates dropped (site boilerplate), curly quotes
     straightened.
  2. Each paragraph through proseweave.analysis with no Jev: the bundled
     parser's tokens, sentences, Penn tags and tag-aware lemmas, with word
     classes from tagger_classes' rules (Analysis.source_lists), then
     source._unit_lists. Keys follow the frequency-list
     lemma convention in which the possessive determiners and "an" are forms of
     their pronoun or article (their -> they, his -> he, our -> we, your -> you,
     an -> a).
  3. Counts per corpus group: lemma unigrams (all, noun, adj, verb incl. aux,
     verb+noun); lemma n-grams (2-4) within sentences; masked n-grams (n, adj,
     v, v_n, a_n) with every other word replaced by the mask symbol "_", which
     no word can equal (the lemma "x" stays an ordinary word).
  4. Groups summed (weights in WEIGHTS), pruned at a floor in
     occurrences per million, and packed with a shared vocabulary.

Needs (build time): numpy, pyarrow; PROSEWEAVE_SRC (default ../src) is the package counted with.
    python build_mag_news_freq.py download
    python build_mag_news_freq.py tag       # -> work/shard_*.pkl  (~40 min on 11 cores)
    python build_mag_news_freq.py count     # -> work/counts.pkl
    python build_mag_news_freq.py pack      # -> mag_news_freq.bin.xz
"""
from __future__ import annotations

import gzip
import json
import lzma
import multiprocessing as mp
import os
import pickle
import re
import struct
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
WORK = HERE / "work"
PROSEWEAVE_SRC = os.environ.get("PROSEWEAVE_SRC", str(HERE.parent / "src"))
sys.path.insert(0, PROSEWEAVE_SRC)

HF = "https://huggingface.co/datasets/common-pile"
SOURCES = {
    "news_filtered.json.gz": f"{HF}/news_filtered/resolve/main/news-dolma-0000.json.gz",
    "wikinews_en.parquet":
        "https://huggingface.co/api/datasets/izumi-lab/wikinews-en-20230728/parquet/default/train/0.parquet",
    "foodista.json.gz": f"{HF}/foodista_filtered/resolve/main/foodista-dolma-0000.json.gz",
    "gutenberg0.json.gz": f"{HF}/project_gutenberg_filtered/resolve/main/project_gutenberg-dolma-0000.json.gz",
}
GROUPS = ["globalvoices", "news", "wikinews", "foodista", "gutenberg"]
# Group weights for the shipped tables. Equal weights were chosen over six
# mixes on the even-indexed validation sources (both validation corpora); down-weighting
# Global Voices or dropping a group scored lower.
WEIGHTS = {"globalvoices": 1.0, "news": 1.0, "wikinews": 1.0, "foodista": 1.0, "gutenberg": 1.0}
FLOOR_PM = 0.253                      # keep items at or above this many per million
# (0.253 rather than 0.25: it drops only the four-word sequences seen 13 times, which
# keeps the packed table within the size of the one it replaced)
GUTENBERG_WORDS, GUTENBERG_PER_BOOK = 10_000_000, 100_000
WIKINEWS_CUT = ("Have an opinion on this story?", "Share this:", "This page is archived",
                "From Wikinews, the free news source")
CONVENTION = {"their": "they", "his": "he", "our": "we", "your": "you", "an": "a"}
MASK = "_"                            # the mask symbol: no kept token is ever "_" (tokens need a letter or digit)
LITERAL_X = "\x00x"                   # the lemma "x" during counting (id 0 is the mask); packed as "x"
NOUN, ADJ, VERB = 1, 2, 4             # class bits per kept token
MASKS = {"n": NOUN, "adj": ADJ, "v": VERB, "v_n": NOUN | VERB, "a_n": NOUN | ADJ}
QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


# -- 1. corpus ------------------------------------------------------------------
def download():
    RAW.mkdir(exist_ok=True)
    for fn, url in SOURCES.items():
        if not (RAW / fn).exists():
            print("fetch", url)
            urllib.request.urlretrieve(url, RAW / fn)


def paragraphs():
    """(group index, paragraph) for every corpus paragraph once, in a fixed order."""
    seen = set()

    def emit(g, parts):
        for p in parts:
            p = p.strip().translate(QUOTES)
            if len(p) < 20:
                continue
            h = hash(p)
            if h not in seen:
                seen.add(h)
                yield GROUPS.index(g), p

    with gzip.open(RAW / "news_filtered.json.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if "Share-Alike" in d["metadata"].get("license", "") or "Attribution" not in d["metadata"].get("license", ""):
                continue
            g = "globalvoices" if d["source"] == "news-globalvoices" else "news"
            yield from emit(g, d["text"].split("\n"))
    import pyarrow.parquet as pq
    for r in pq.read_table(RAW / "wikinews_en.parquet", columns=["title", "text"]).to_pylist():
        if ":" in (r["title"] or "").split(" ")[0]:          # Category:, Wikinews:, Portal: ...
            continue
        t = r["text"] or ""
        for c in WIKINEWS_CUT:
            i = t.find(c)
            if i >= 0:
                t = t[:i]
        yield from emit("wikinews", t.split("\n"))
    with gzip.open(RAW / "foodista.json.gz", "rt", encoding="utf-8") as f:
        for line in f:
            yield from emit("foodista", json.loads(line)["text"].split("\n"))
    words = 0
    with gzip.open(RAW / "gutenberg0.json.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["metadata"].get("license") != "Public Domain" or "Bible" in d["metadata"].get("title", ""):
                continue
            n = 0
            for p in re.split(r"\n\s*\n", d["text"]):
                p = " ".join(p.split())
                n += p.count(" ") + 1
                if n > GUTENBERG_PER_BOOK:
                    break
                yield from emit("gutenberg", [p])
            words += min(n, GUTENBERG_PER_BOOK)
            if words >= GUTENBERG_WORDS:
                break


# -- 2. tagging -----------------------------------------------------------------
def _tag_chunk(args):
    """Kept tokens of each paragraph exactly as proseweave's source comparison reads a
    text: Analysis.source_lists with no Jev (the bundled parser's tokens, sentences,
    Penn tags and lemmas; rule-based word classes), then source._unit_lists."""
    idx, items = args
    from proseweave import analysis, source
    lemmas, bits, ends, groups = [], bytearray(), bytearray(), bytearray()
    for g, p in items:
        L = analysis.Analysis(p, None).source_lists()
        _, per_sent = source._unit_lists(L)
        for seq in per_sent:
            if not seq:
                continue
            for lemma, c in seq:
                lem = CONVENTION.get(lemma, lemma)
                lemmas.append(LITERAL_X if lem == "x" else lem)
                bits.append((NOUN if c["noun"] else 0) | (ADJ if c["adj"] else 0) | (VERB if c["verb_all"] else 0))
                ends.append(0)
                groups.append(g)
            ends[-1] = 1
    with open(WORK / f"shard_{idx:05d}.pkl", "wb") as f:
        pickle.dump((lemmas, bytes(bits), bytes(ends), bytes(groups)), f, protocol=5)
    return len(lemmas)


def tag(workers=11, chunk=4000):
    WORK.mkdir(exist_ok=True)
    for old in WORK.glob("shard_*.pkl"):
        old.unlink()

    def chunks():
        buf, i = [], 0
        for item in paragraphs():
            buf.append(item)
            if len(buf) == chunk:
                yield i, buf
                buf, i = [], i + 1
        if buf:
            yield i, buf

    total = 0
    with mp.get_context("spawn").Pool(workers) as pool:
        for n in pool.imap_unordered(_tag_chunk, chunks()):
            total += n
            print(f"\r{total:,} tokens", end="", flush=True)
    print()


# -- 3. counting ----------------------------------------------------------------
def _load_stream():
    import numpy as np
    vocab = {MASK: 0}                 # id 0 is the mask
    lem, bits, ends, grp = [], [], [], []
    for fn in sorted(WORK.glob("shard_*.pkl")):
        L, b, e, g = pickle.load(open(fn, "rb"))
        lem.append(np.fromiter((vocab.setdefault(w, len(vocab)) for w in L), dtype=np.int64, count=len(L)))
        bits.append(np.frombuffer(b, dtype=np.uint8))
        ends.append(np.frombuffer(e, dtype=np.uint8))
        grp.append(np.frombuffer(g, dtype=np.uint8))
    return vocab, np.concatenate(lem), np.concatenate(bits), np.concatenate(ends), np.concatenate(grp)


def _grams(ids, ends, n):
    """(N, 2) uint64 keys of every within-sentence n-gram (21 bits per slot), and
    the index of each n-gram's first token."""
    import numpy as np
    sent = np.concatenate([[0], np.cumsum(ends[:-1])])
    N = len(ids) - n + 1
    ok = sent[:N] == sent[n - 1:]
    cols = [ids[k:k + N][ok] for k in range(n)]
    hi = cols[0] << 21 | cols[1]
    if n >= 3:
        hi = hi << 21 | cols[2]
    lo = cols[3] if n == 4 else np.zeros_like(hi)
    return np.stack([hi, lo], axis=1).astype(np.uint64), np.nonzero(ok)[0]


def _count(keys, first, grp, floor=3):
    """Unique keys with count >= floor, their per-group counts, per-group totals."""
    import numpy as np
    v = np.ascontiguousarray(keys).view("V16").ravel()
    u, inv, c = np.unique(v, return_inverse=True, return_counts=True)
    keep = c >= floor
    g = grp[first]
    per = np.stack([np.bincount(inv[g == k], minlength=len(u))[keep] for k in range(len(GROUPS))], 1)
    tot = np.array([(g == k).sum() for k in range(len(GROUPS))])
    return u[keep].view(np.uint64).reshape(-1, 2), per.astype(np.int32), tot


def count():
    import numpy as np
    vocab, ids, bits, ends, grp = _load_stream()
    print(f"{len(ids):,} tokens, {len(vocab):,} lemma types")
    assert len(vocab) < 1 << 21
    tot_g = np.array([(grp == k).sum() for k in range(len(GROUPS))])
    print({g: int(t) for g, t in zip(GROUPS, tot_g)})
    uni = {}
    for cname, mask in (("all", 0), ("noun", NOUN), ("adj", ADJ), ("verb_all", VERB), ("verb_noun", NOUN | VERB)):
        sel = np.ones(len(ids), bool) if not mask else (bits & mask) > 0
        per = np.stack([np.bincount(ids[sel & (grp == k)], minlength=len(vocab)) for k in range(len(GROUPS))], 1)
        uni[cname] = (per.astype(np.int32), np.array([(sel & (grp == k)).sum() for k in range(len(GROUPS))]))
    out = {"vocab": vocab, "uni": uni, "groups": GROUPS}
    for n in (2, 3, 4):
        k, first = _grams(ids, ends, n)
        out[("plain", n)] = _count(k, first, grp)
        for m, keep in MASKS.items():
            masked = np.where((bits & keep) > 0, ids, 0)
            k, first = _grams(masked, ends, n)
            kk, per, tot = _count(k, first, grp)
            allx = (kk[:, 0] == 0) & (kk[:, 1] == 0)
            out[(m, n)] = (kk[~allx], per[~allx], tot)
        print("counted", n, flush=True)
    pickle.dump(out, open(WORK / "counts.pkl", "wb"), protocol=5)


# -- 4. packing -----------------------------------------------------------------
def _decode(k, n):
    import numpy as np
    if n == 1:
        return k.reshape(-1, 1).astype(np.int64)
    hi, lo, M = k[:, 0].astype(np.int64), k[:, 1].astype(np.int64), (1 << 21) - 1
    if n == 2:
        return np.stack([hi >> 21 & M, hi & M], 1)
    if n == 3:
        return np.stack([hi >> 42 & M, hi >> 21 & M, hi & M], 1)
    return np.stack([hi >> 42 & M, hi >> 21 & M, hi & M, lo], 1)


_C = None


def _counts():
    global _C
    if _C is None:
        _C = pickle.load(open(WORK / "counts.pkl", "rb"))
    return _C


def weighted(per, weights=None):
    import numpy as np
    w = np.array([(weights or WEIGHTS)[g] for g in GROUPS], dtype=np.float64)
    return per @ w


def xz(blob: bytes) -> bytes:
    """Maximum compression with an 8 MiB dictionary: 2% larger than preset 9's 64 MiB
    one for this table, and the reader needs 8 MiB to decode it instead of 64."""
    return lzma.compress(blob, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64,
                         filters=[{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME,
                                   "dict_size": 1 << 23}])


def pack(floor_pm=FLOOR_PM, weights=None, out_path=None):
    """Weighted counts at or above `floor_pm` per million (of their table's weighted
    total), rounded to integers.

    Binary layout (then xz): b"PWMN", <u32 header length, u32 vocab length>, JSON
    header {format: 2, vocab_size, floor_pm, tables: [[name, n, total, entries]]},
    the vocabulary (NUL-separated UTF-8 lemmas, id 0 = the mask "_", common lemmas first),
    then per table, rows sorted by id tuple, stored as columns: n little-endian
    id columns (uint16, or uint32 when id_bytes is 4), then a uint32 count column. A reader can binary-search the
    columns in place, so loading does no per-entry work.
    """
    import numpy as np
    C = _counts()
    vocab = C["vocab"]
    names = [""] * len(vocab)
    for w, i in vocab.items():
        names[i] = w
    tables = []
    per, tot = C["uni"]["all"]
    c, t = weighted(per, weights), weighted(tot[None, :], weights)[0]
    ids = np.nonzero(c >= max(1.0, floor_pm * t / 1e6))[0]
    ids = ids[ids != 0]
    tables.append(("uni_all", 1, t, ids.reshape(-1, 1), c[ids]))
    for key, val in C.items():
        if not isinstance(key, tuple):
            continue
        (m, n), (k, per, tot) = key, val
        c, t = weighted(per, weights), weighted(tot[None, :], weights)[0]
        sel = c >= max(1.0, floor_pm * t / 1e6)
        tables.append((f"{m}_{n}", n, t, _decode(k[sel], n), c[sel]))
    used = np.zeros(len(vocab), bool)
    used[0] = True
    for *_, tup, _ in tables:
        used[np.unique(tup)] = True
    allc = weighted(C["uni"]["all"][0], weights)
    allc[0] = np.inf
    order = [i for i in np.argsort(-allc, kind="stable").tolist() if used[i]]   # common lemmas get small ids
    remap = np.full(len(vocab), -1, np.int64)
    remap[order] = np.arange(len(order))
    V = len(order)
    id_type = "<u2" if V < 1 << 16 else "<u4"
    body = bytearray()
    header = {"format": 2, "vocab_size": V, "id_bytes": int(id_type[-1]), "floor_pm": floor_pm, "tables": []}
    for name, n, t, tup, c in tables:
        ids = remap[tup]
        order_rows = np.lexsort(ids.T[::-1])                 # lexicographic by id tuple
        ids, cnt = ids[order_rows], np.maximum(1, np.rint(c[order_rows])).astype("<u4")
        for col in range(n):
            body += ids[:, col].astype(id_type).tobytes()
        body += cnt.tobytes()
        header["tables"].append([name, n, int(round(t)), len(ids)])
    words = [MASK if i == 0 else names[i].replace(LITERAL_X, "x") for i in order]
    assert all("\0" not in w for w in words) and words.count(MASK) == 1
    vocab_bytes = "\0".join(words).encode("utf-8")
    hb = json.dumps(header).encode()
    blob = b"PWMN" + struct.pack("<II", len(hb), len(vocab_bytes)) + hb + vocab_bytes + bytes(body)
    out_path = Path(out_path or HERE / "mag_news_freq.bin.xz")
    out_path.write_bytes(xz(blob))
    print(f"{out_path.name}: {out_path.stat().st_size / 1e6:.2f} MB, vocab {V:,}, "
          f"{sum(t[3] for t in header['tables']):,} entries")
    for t in header["tables"]:
        print("  ", t[:4])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("download", "all"):
        download()
    if cmd in ("tag", "all"):
        tag()
    if cmd in ("count", "all"):
        count()
    if cmd in ("pack", "all"):
        pack(*(float(a) for a in sys.argv[2:3]))
