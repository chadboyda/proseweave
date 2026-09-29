"""Build data/zipf_en.bin.gz: word -> Zipf value from CC BY and public-domain text (build-time only).

    python3 build_zipf_table.py count   -> work/wf_counts.pkl  {source: Counter}
    python3 build_zipf_table.py pack    -> work/zipf_en.tsv.gz (equal weights, min count 5), then
                                           data/zipf_en.bin.gz via tools/pack_tables.py

Sources and licences:
  news       Common Pile news_filtered, CC BY articles only        (CC BY)
  wikinews   English Wikinews 2023-07-28                            (CC BY 2.5)
  foodista   Common Pile Foodista                                   (CC BY 3.0)
  gutenberg  Common Pile Project Gutenberg sample                   (public domain)
  youtube    Common Pile YouTube Commons, first shard, CC BY only   (CC BY 4.0)
Streamed shards are read up to CAP tokens each. Paragraphs found in the open
validation corpus are skipped.
"""
import collections, gzip, io, json, math, pathlib, pickle, re, sys, urllib.request

HERE = pathlib.Path(__file__).resolve().parent            # tools/, next to build_mag_news_freq.py
sys.path.insert(0, str(HERE))
OPEN = HERE.parent / "validation" / "open" / "texts"      # held out of the counts
WORK = HERE / "work"
WORD = re.compile(r"[a-z]+")
CAP = 40_000_000
HF = "https://huggingface.co/datasets/common-pile"
STREAMS = {
    "youtube": (f"{HF}/youtube_filtered/resolve/main/youtube-commons-0000.json.gz", "Attribution -"),
}
GROUP = {"news": "news", "globalvoices": "news", "wikinews": "wikinews", "foodista": "foodista",
         "gutenberg": "gutenberg"}


def held_out():
    import build_mag_news_freq as bm
    held = set()
    for p in OPEN.glob("*.txt"):
        for para in p.read_text(encoding="utf-8").split("\n"):
            para = para.strip().translate(bm.QUOTES)
            if len(para) >= 20:
                held.add(hash(para))
    return held


def count():
    import build_mag_news_freq as bm
    WORK.mkdir(exist_ok=True)
    held = held_out()
    counts = collections.defaultdict(collections.Counter)
    for g, para in bm.paragraphs():
        if hash(para) not in held:
            counts[GROUP.get(bm.GROUPS[g], bm.GROUPS[g])].update(WORD.findall(para.lower()))
    print({k: sum(v.values()) for k, v in counts.items()}, flush=True)
    for name, (url, lic) in STREAMS.items():
        n = 0
        with urllib.request.urlopen(url) as r, gzip.open(r, "rt", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                lic_d = d.get("metadata", {}).get("license", "")
                if lic not in lic_d or any(x in lic_d for x in ("NonCommercial", "NoDeriv", "Share-Alike", "ShareAlike")):
                    continue
                for para in d["text"].split("\n"):
                    para = para.strip().translate(bm.QUOTES)
                    if len(para) < 20 or hash(para) in held:
                        continue
                    ws = WORD.findall(para.lower())
                    counts[name].update(ws); n += len(ws)
                if n >= CAP:
                    break
        print(name, n, flush=True)
    pickle.dump(dict(counts), open(WORK / "wf_counts.pkl", "wb"))


def combined(weights, min_count=3):
    counts = pickle.load(open(WORK / "wf_counts.pkl", "rb"))
    freq = collections.Counter()
    raw = collections.Counter()
    for src, w in weights.items():
        c = counts[src]; tot = sum(c.values())
        for word, n in c.items():
            freq[word] += w * n / tot
            raw[word] += n
    s = sum(weights.values())
    return {word: math.log10(f / s * 1e9) for word, f in freq.items() if raw[word] >= min_count}


WEIGHTS = {"news": 1, "wikinews": 1, "foodista": 1, "gutenberg": 1, "youtube": 1}


def pack(weights=WEIGHTS, out=HERE / "work" / "zipf_en.tsv.gz", min_count=5):
    z = {w: v for w, v in combined(weights, min_count).items() if len(w) <= 24}
    out.parent.mkdir(exist_ok=True)
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as f:
        f.write("#zipf\tlog10 frequency per billion words; sources: " + ", ".join(weights) +
                " (equal weights); min count " + str(min_count) + "\n")
        for w, v in sorted(z.items(), key=lambda x: -x[1]):
            f.write(f"{w}\t{v:.1f}\n")
    print(len(z), "words", round(out.stat().st_size / 1e6, 2), "MB")
    import pack_tables
    pack_tables.zipf(out)          # -> data/zipf_en.bin.gz, the form proseweave reads


if __name__ == "__main__":
    if sys.argv[1] == "count":
        count()
    else:
        pack()
