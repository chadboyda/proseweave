#!/usr/bin/env python3
"""Fetch open-licensed raw text for distilling the parser.

Sources (text is used only to train weights; none of it ships):
  - English Wikipedia, random articles (CC BY-SA 4.0)
  - English Wikinews, random articles (CC BY 2.5)
  - Project Gutenberg books (public domain in the US)
  - UD English EWT raw sentences (CC BY-SA 4.0), rebuilt into documents
Writes data/text/{wiki,wikinews,gutenberg,ewt}/NNNN.txt

    python3 fetch_text.py [N_WIKI] [N_WIKINEWS]
"""
import concurrent.futures as cf
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parents[2] / "build" / "syntax"
OUT = HERE / "text"
UA = {"User-Agent": "proseweave-build/0.1 (+https://github.com/chadboyda/proseweave)"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


SITES = {"wiki": ("en.wikipedia.org", 12000), "wikinews": ("en.wikinews.org", 2500)}


def wiki_titles(n, site="wiki"):
    """Random articles long enough to be prose (by wikitext length)."""
    host, min_len = SITES[site]
    titles = []
    while len(titles) < n:
        q = urllib.parse.urlencode({"action": "query", "generator": "random", "grnnamespace": 0,
                                    "grnlimit": 500, "prop": "info", "format": "json"})
        try:
            d = json.loads(get(f"https://{host}/w/api.php?" + q))
        except Exception:
            continue
        titles += [p["title"] for p in d["query"]["pages"].values() if p.get("length", 0) >= min_len]
    return titles[:n]


def wiki_one(arg):
    site, k, title = arg
    host = SITES[site][0]
    p = OUT / site / f"{k:04d}.txt"
    if p.exists():
        return
    for _ in range(3):
        try:
            q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "extracts",
                                        "explaintext": 1, "format": "json"})
            d = json.loads(get(f"https://{host}/w/api.php?" + q))
            page = next(iter(d["query"]["pages"].values()))
            txt = page.get("extract", "")
            if len(txt.split()) >= (250 if site == "wiki" else 150):
                p.write_text(page["title"] + "\n\n" + txt, encoding="utf-8")
            return
        except Exception:
            pass


GUTENBERG = [1342, 84, 2701, 1661, 98, 11, 74, 76, 345, 1400, 768, 5200, 2554, 219, 1260, 158, 161, 205,
             1232, 3207, 4300, 2600, 145, 1184, 25344, 16328, 5827, 7370, 4363, 2680, 1497, 10615, 1250,
             8800, 30254, 35, 36, 1952, 6130, 16389]


def gut_one(n):
    p = OUT / "gutenberg" / f"{n}.txt"
    if p.exists():
        return
    try:
        t = get(f"https://www.gutenberg.org/cache/epub/{n}/pg{n}.txt")
    except Exception:
        return
    s = re.search(r"\*\*\* ?START OF.*?\*\*\*", t)
    e = re.search(r"\*\*\* ?END OF", t)
    t = t[s.end() if s else 0: e.start() if e else len(t)]
    # Gutenberg hard-wraps lines; rejoin paragraphs so newlines look like modern text.
    paras = [" ".join(x.split()) for x in re.split(r"\n\s*\n", t) if x.strip()]
    words = 0
    keep = []
    for para in paras:
        keep.append(para)
        words += len(para.split())
        if words > 60000:
            break
    p.write_text("\n\n".join(keep), encoding="utf-8")


def ewt():
    d = OUT / "ewt"
    d.mkdir(parents=True, exist_ok=True)
    docs, cur, par = [], [], []
    for line in open(HERE / "en_ewt-ud-train.conllu", encoding="utf-8"):
        if line.startswith("# newdoc"):
            if par:
                cur.append(" ".join(par))
            if cur:
                docs.append("\n\n".join(cur))
            cur, par = [], []
        elif line.startswith("# newpar"):
            if par:
                cur.append(" ".join(par))
            par = []
        elif line.startswith("# text = "):
            par.append(line[9:].strip())
    if par:
        cur.append(" ".join(par))
    if cur:
        docs.append("\n\n".join(cur))
    for i, t in enumerate(docs):
        (d / f"{i:04d}.txt").write_text(t, encoding="utf-8")
    print("ewt docs", len(docs))


if __name__ == "__main__":
    want = {"wiki": int(sys.argv[1]) if len(sys.argv) > 1 else 1500,
            "wikinews": int(sys.argv[2]) if len(sys.argv) > 2 else 0}
    for sub in ("wiki", "wikinews", "gutenberg"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    ewt()
    with cf.ThreadPoolExecutor(3) as ex:
        list(ex.map(gut_one, GUTENBERG))
        for site, n in want.items():
            if n:
                start = len(list((OUT / site).glob("*.txt")))
                list(ex.map(wiki_one, [(site, start + k, t) for k, t in enumerate(wiki_titles(n, site))]))
    print({s: len(list((OUT / s).glob("*.txt"))) for s in ("wiki", "wikinews", "gutenberg")})
