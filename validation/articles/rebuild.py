#!/usr/bin/env python3
"""Rebuild the article validation corpus from its public sources.

The 104 article excerpts in this corpus are copyrighted, so they are not
distributed. `manifest.json` lists each source URL, its category, and the
SHA-256 of the exact excerpt that was measured. This script fetches each page,
extracts its body text, cuts it to the same excerpt with the same rule, and
reports whether the result matches the recorded hash.

    python3 rebuild.py OUT_DIR                 fetch, extract, clip, verify
    python3 rebuild.py OUT_DIR --from DIR      clip pre-extracted text (DIR/NNN.txt)

Web pages change and extractors differ, so an exact hash match is not
guaranteed. A rebuilt excerpt that differs slightly still measures almost the
same; results computed on a rebuilt corpus are reported alongside the match
count. Four texts are the author's own unpublished writing and are not
available.

Standard library only. Respect each site's terms when fetching.
"""
from __future__ import annotations

import hashlib
import html.parser
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def clip(t: str, limit: int = 900):
    """Whole paragraphs up to ~limit words; an over-long paragraph is cut at a
    sentence boundary. Returns (text, words), or (None, 0) when the paragraph
    structure cannot be recovered."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]

    def unwrap(block):
        out = []
        for line in (ln.strip() for ln in block.splitlines()):
            if not line:
                continue
            if out and not re.search(r"[.!?:\"”’)]$", out[-1]):
                out[-1] += " " + line
            else:
                out.append(line)
        return out

    if len(paras) < 3:
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        if not lines or sum(map(len, lines)) / len(lines) < 120:
            return None, 0
        paras = lines
    else:
        paras = [" ".join(unwrap(p)) for p in paras]
    out, n = [], 0
    for p in paras:
        words = len(p.split())
        if n + words > limit * 1.15:
            room = limit - n
            if room < 40:
                break
            keep, k = [], 0
            for s in re.split(r"(?<=[.!?])\s+", p):
                if k + len(s.split()) > room:
                    break
                keep.append(s)
                k += len(s.split())
            if keep:
                out.append(" ".join(keep))
                n += k
            break
        out.append(p)
        n += words
        if n >= limit:
            break
    return "\n\n".join(out) + "\n", n


class _Paragraphs(html.parser.HTMLParser):
    """Collect the text of <p> elements, preferring those inside <article>."""

    def __init__(self):
        super().__init__()
        self.depth = {"article": 0, "p": 0, "skip": 0}
        self.cur, self.all, self.article = [], [], []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "aside", "figcaption"):
            self.depth["skip"] += 1
        elif tag == "article":
            self.depth["article"] += 1
        elif tag == "p":
            self.depth["p"] += 1
            self.cur = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "aside", "figcaption"):
            self.depth["skip"] = max(0, self.depth["skip"] - 1)
        elif tag == "article":
            self.depth["article"] = max(0, self.depth["article"] - 1)
        elif tag == "p" and self.depth["p"]:
            self.depth["p"] -= 1
            text = re.sub(r"\s+", " ", "".join(self.cur)).strip()
            if len(text.split()) >= 8:
                self.all.append(text)
                if self.depth["article"]:
                    self.article.append(text)

    def handle_data(self, data):
        if self.depth["p"] and not self.depth["skip"]:
            self.cur.append(data)


def extract(page: str) -> str:
    p = _Paragraphs()
    p.feed(page)
    paras = p.article if len(p.article) >= 3 else p.all
    return "\n\n".join(paras)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (proseweave validation rebuild)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if not a:
        print(__doc__)
        return 2
    out = Path(a[0])
    src = Path(a[a.index("--from") + 1]) if "--from" in a else None
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    match = built = 0
    for m in manifest:
        if not m.get("url"):
            continue
        try:
            raw = (src / m["file"]).read_text(encoding="utf-8") if src else extract(fetch(m["url"]))
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"{m['file']}: unavailable ({e.__class__.__name__})")
            continue
        body, _ = clip(raw)
        if body is None:
            print(f"{m['file']}: no recoverable paragraphs")
            continue
        (out / m["file"]).write_text(body, encoding="utf-8")
        built += 1
        ok = hashlib.sha256(body.encode("utf-8")).hexdigest() == m["sha256"]
        match += ok
        print(f"{m['file']}: {'exact' if ok else 'rebuilt (differs from the measured excerpt)'}")
    print(f"{built} rebuilt, {match} exact matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
