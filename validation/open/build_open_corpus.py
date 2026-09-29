#!/usr/bin/env python3
"""Build the open-licensed proseweave validation corpus (108 texts, 27 x 4).

Every text is public domain, CC0, CC BY or CC BY-SA. Nothing here is NC or ND.

Sources
-------
* Common Pile v0.1 (EleutherAI, https://huggingface.co/common-pile), the
  "_filtered" subsets, fetched one row at a time through the Hugging Face
  datasets-server API:

      https://datasets-server.huggingface.co/rows?dataset=common-pile/<subset>
          &config=default&split=train&offset=<row>&length=1

  `offset` is the row index in the datasets-server's converted parquet
  (refs/convert/parquet). For the large subsets that conversion is
  "partial-train", so only rows in the converted part are addressable; every
  offset below was chosen from inside it. Subsets used (all "_filtered"):
  project_gutenberg (62 texts), news (11: 360info, Global Voices, Milwaukee
  Neighborhood News Service, Oxpeckers), public_domain_review (10),
  pubmed (3, J Med Case Reports) and python_enhancement_proposals (2).
  The license recorded for each document is the one in the row's own
  `metadata.license` field (Gutenberg and PEPs: "Public Domain"; PDR:
  CC BY-SA 4.0, but PDR items are recorded as CC BY-SA 3.0, as stated by the
  publisher, see PUBLISHER_LICENSE; news: CC BY 4.0 or CC BY-SA 4.0 per article; PubMed: CC BY
  4.0 per article). license_of() refuses any other value.

How the rows were chosen: titles and metadata were scanned (Gutenberg titles,
news URLs/headlines, PDR essay list, PubMed journal names), candidates were
opened, and the start anchor was set at the first body paragraph of a
section. Candidates were dropped when the recovered text had fewer than
three real paragraphs, was mostly a list/glossary/lab table, quoted long
passages in other languages, or was partner content republished by the
outlet under a separate agreement.
* Synthetic texts (license CC0-1.0, source "synthetic") for the commercial
  register categories no open source covers: listicle, social post, SEO
  article, press release and corporate blog. They were generated with an LLM
  for this corpus and are not fetched; the
  script leaves texts/NNN.txt for those entries untouched and only checks
  their hashes. All names in them are fictional.

Rows are cached in $PW_CACHE (default: a folder in the system temp dir).

Selection
---------
Each SPEC entry names a row, a literal `start` anchor (the text is cut from
its first occurrence, after `skip` earlier occurrences) and an optional
`end` anchor. The slice is cleaned (markup, footnote markers, headings,
captions, verse and block quotes, reference lists removed), turned into
blank-line-separated paragraphs, then passed to clip(), which applies the
same clip rule as validation/articles/rebuild.py.

Usage
-----
    python3 build_open_corpus.py            # fetch, rebuild texts/, manifest
    python3 build_open_corpus.py --check    # rebuild in memory, compare hashes
    python3 build_open_corpus.py --only 12  # preview one entry on stdout

Standard library only.
"""
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
TEXTS = HERE / "texts"
CACHE = pathlib.Path(os.environ.get("PW_CACHE") or
                     os.path.join(tempfile.gettempdir(), "proseweave-open-corpus-cache"))
ROWS = "https://datasets-server.huggingface.co/rows"

# --------------------------------------------------------------------------
# Fetch
# --------------------------------------------------------------------------


def fetch_row(subset, offset):
    """One Common Pile row via the datasets-server /rows endpoint (cached)."""
    fn = CACHE / f"{subset}_{offset}.json"
    if fn.exists():
        return json.loads(fn.read_text())
    CACHE.mkdir(parents=True, exist_ok=True)
    url = (f"{ROWS}?dataset=common-pile/{subset}&config=default&split=train"
           f"&offset={offset}&length=1")
    last = None
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "proseweave-open-corpus"})
            with urllib.request.urlopen(req, timeout=180) as r:
                row = json.load(r)["rows"][0]["row"]
            fn.write_text(json.dumps(row))
            return row
        except Exception as e:  # 502s are common on big rows; back off
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"fetch failed {subset}@{offset}: {last}")


# --------------------------------------------------------------------------
# Clip rule (the same clip rule as validation/articles/rebuild.py)
# --------------------------------------------------------------------------


def clip(t, limit=900):
    """Keep whole paragraphs up to ~limit words, so paragraph indices stay real.

    Some sources have no blank lines at all, so a "paragraph" can be the whole
    article. Treat single newlines as paragraph breaks when there are no blank
    ones, and cut an over-long paragraph at a sentence boundary.
    """
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    # Undo hard wrapping inside a paragraph: a line that does not end a
    # sentence continues onto the next one.
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
            # Hard-wrapped with no blank lines: the paragraph structure is not
            # recoverable, and inventing one would make every paragraph index
            # meaningless. Skip the text.
            return None, 0
        paras = lines          # one paragraph per (long) line
    else:
        paras = [" ".join(unwrap(p)) for p in paras]
    out, n = [], 0
    for p in paras:
        words = len(p.split())
        if n + words > limit * 1.15:
            room = limit - n
            if room < 40:
                break
            sents = re.split(r"(?<=[.!?])\s+", p)
            keep, k = [], 0
            for s in sents:
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


# --------------------------------------------------------------------------
# Cleaning. Each returns blank-line-separated paragraphs for clip().
# --------------------------------------------------------------------------

END_PUNCT = re.compile(r"[.!?:;\"”’)\]—-]$")


def _inline(p):
    p = re.sub(r"\[(?:Footnote|Illustration|Sidenote)[^\]]*\]", "", p)
    p = re.sub(r"\[\d+\]|\{\d+\}|\[[A-Z]\]", "", p)       # [12] [A] {3} markers
    p = re.sub(r"^\[[A-Z .]+\]\s*", "", p)                  # "[INTRODUCTORY NOTE.] ..."
    p = re.sub(r"(?<=[a-z][.,;:”’\")])\d{1,3}(?=\s|$)", "", p)  # "word.12" footnotes
    p = re.sub(r"(?<![\w_])_([^_\n]+?)_(?![\w_])", r"\1", p)  # _italics_ (not __dunder__)
    p = re.sub(r"\[(?:[a-z]{2}|[A-Z]{2})\]", "", p)       # Global Voices [es]
    p = re.sub(r"https?://\S+", "", p)
    p = re.sub(r"[ \t  ​]+", " ", p)
    return p.strip()


def _junk(p):
    """Captions, plates, embeds, list items and non-English quotations."""
    if re.search(r"pic\.twitter\.com|\(Photo(?:s|graph)? (?:by|:|courtesy)|\bPhotos?: |photographed here", p):
        return True
    if re.match(r"^\s*(\[.*\]\]?|\(.*\))\s*$", p, re.S):           # [plate note] / (To face page 23.)
        return True
    if re.match(r"^\d{1,3}\.\s", p):                                  # numbered list / glossary item
        return True
    letters = re.findall(r"[^\W\d_]", p)
    if letters and sum(1 for c in letters if ord(c) > 0x24F) / len(letters) > 0.2:
        return True                                                   # Cyrillic, Arabic, CJK quotes
    return False


def _heading(p):
    w = p.split()
    if not w:
        return True
    if _junk(p):
        return True
    letters = re.sub(r"[^A-Za-z]", "", p)
    if letters and letters.isupper() and len(w) < 16:
        return True
    if len(w) < 12 and not END_PUNCT.search(p):
        return True
    if re.match(r"^(CHAPTER|Chapter|BOOK|PART|LECTURE|SECTION)\b", p) and len(w) < 14:
        return True
    return False


def clean_blocks(text):
    """Gutenberg-style text: blank lines separate paragraphs, lines hard-wrapped."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        # verse, block quotes, tables: every line indented
        if all(re.match(r"^\s{2,}", ln) for ln in lines):
            continue
        if re.match(r"^\s*\[?(Footnote|Illustration|Sidenote)", lines[0]):
            continue
        p = " ".join(ln.strip() for ln in lines)
        p = _inline(p)
        if not p or _heading(p):
            continue
        out.append(p)
    return "\n\n".join(out)


CAPTION = re.compile(r"^(Image|Photo|Photograph|Screenshot|Screen ?grab|Featured image|"
                     r"Source|Credit|Read more|Related|This article|This story|"
                     r"Originally published|Follow|Subscribe|Editor's note|Sign up)", re.I)


def clean_lines(text, drop_head=0):
    """News / PDR style: one paragraph per line (sometimes with blank lines)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    lines = lines[drop_head:]
    out = []
    for ln in lines:
        p = _inline(ln)
        if not p or _heading(p) or CAPTION.match(p):
            continue
        if re.search(r"(used with permission|CC BY|Creative Commons|All rights reserved)", p, re.I) and len(p.split()) < 40:
            continue
        out.append(p)
    return "\n\n".join(out)


def clean_markdownish(text):
    """PEPs / StackExchange: drop code, lists, tables, headings."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if any(re.match(r"^\s{4,}|^\s*[-*+]\s|^\s*\d+\.\s|^\s*[|>]|^```|^\s*::", ln) for ln in lines):
            continue
        p = _inline(" ".join(ln.strip() for ln in lines))
        p = re.sub(r"`([^`]*)`", r"\1", p)
        p = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", p)
        if not p or _heading(p):
            continue
        out.append(p)
    return "\n\n".join(out)


def clean_pmc(text):
    """PubMed Central (pandoc markdown, one paragraph per line)."""
    keep, drop_next = [], False
    for ln in text.splitlines():            # "::: {#F1 .fig}" + caption line
        if drop_next:
            drop_next = False
            continue
        if ln.startswith(":::"):
            drop_next = "{" in ln
            continue
        if re.match(r"^\s*(#+ |!\[)", ln):
            continue
        keep.append(ln)
    t = "\n".join(keep)
    t = re.sub(r"\[\^\d+\]", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)(?:\{[^}]*\})?", r"\1", t)     # [text](link){..}
    t = t.replace("**", "")
    t = t.replace("\\[", "[").replace("\\]", "]")
    t = re.sub(r"\s*\[\s*(?:\[@[^\]]*\][,\s\-–]*)+\](?:\s*[-–]\s*\[\s*(?:\[@[^\]]*\][,\s]*)+\])*", "", t)
    t = re.sub(r"\s*\[<EMAIL_ADDRESS>|<EMAIL_ADDRESS>", "", t)
    t = re.sub(r"\s*\(\[(?:Figure|Table|Fig)[^)]*\)\{[^}]*\}\)?", "", t)  # ([Figure 1](#..){..})
    t = re.sub(r"\[([^\]]+)\]\(#[^)]*\)\{[^}]*\}", r"\1", t)
    t = re.sub(r"\{#[^}]*\}", "", t)                                  # heading ids
    t = re.sub(r"\*([^*\n]+)\*", r"\1", t)                            # *italic*
    t = t.replace("\\[", "[").replace("\\]", "]")
    t = re.sub(r"\s*\((?:Figure|Figures|Fig\.|Table|Tables)\s[^)]*\)", "", t)
    out = []
    for ln in t.splitlines():
        p = _inline(ln)
        if re.match(r"^(Written informed consent|The authors? declare|Competing interests|"
                    r"Acknowledg|Authors'? contributions|[A-Z]{2,4} (conceived|postulated|designed|wrote))", p):
            break                                                     # back matter
        if not p or _heading(p) or p.startswith(("!", "|", "Figure", "Table")):
            continue
        out.append(p)
    return "\n\n".join(out)


CLEANERS = {"blocks": clean_blocks, "lines": clean_lines, "md": clean_markdownish, "pmc": clean_pmc}


def _anchor(s):
    # literal words, any whitespace between them (hard wrapping differs)
    return re.compile(r"\s+".join(re.escape(w) for w in s.split()))


def select(text, start, end=None, skip=0):
    """Slice from the (skip+1)-th match of `start` to the next `end` (or EOF)."""
    ms = list(_anchor(start).finditer(text)) if start else []
    if start and len(ms) <= skip:
        raise ValueError(f"start anchor not found: {start[:60]!r}")
    i = ms[skip].start() if start else 0
    # step back to the start of the line so a paragraph is not cut mid-line
    i = text.rfind("\n", 0, i) + 1
    j = len(text)
    if end:
        m = _anchor(end).search(text, i + 1)
        if m:
            j = m.start()
    return text[i:j]


def build_one(e):
    row = fetch_row(e["subset"], e["offset"])
    t = row["text"].replace("\r\n", "\n")
    part = select(t, e["start"], e.get("end"), e.get("skip", 0))
    style = e.get("clean", "blocks")
    body = CLEANERS[style](part) if style != "lines" else clean_lines(part, e.get("drop_head", 0))
    txt, n = clip(body)
    if txt is None:
        raise ValueError("paragraphs not recoverable")
    return txt, n, row


# --------------------------------------------------------------------------
# License and provenance, read from each row's own metadata
# --------------------------------------------------------------------------

LICENSE_IDS = {
    "creativecommons.org/licenses/by/4.0": "CC-BY-4.0",
    "creativecommons.org/licenses/by-sa/4.0": "CC-BY-SA-4.0",
    "creativecommons.org/publicdomain/zero/1.0": "CC0-1.0",
}
LICENSE_URLS = {
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-SA-3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
}
LICENSE_NAMES = {"CC-BY-SA-3.0": "CC BY-SA 3.0"}
# Subsets whose publisher states a different licence from the Common Pile row:
# the publisher's statement is the one recorded, with a note.
PUBLISHER_LICENSE = {
    "public_domain_review_filtered":
        ("CC-BY-SA-3.0", "as stated by the publisher; Common Pile lists CC-BY-SA-4.0"),
}


def license_of(row):
    raw = row["metadata"].get("license", "")
    for k, v in LICENSE_IDS.items():
        if k in raw:
            return v
    if raw.strip().lower() == "public domain":
        return "public-domain"
    raise ValueError(f"unrecognised license {raw!r}")  # anything else (NC, ND, ...) is refused


def source_of(row):
    return row["metadata"].get("url") or row.get("id")


# --------------------------------------------------------------------------
# Selection: 27 categories x 4. `offset` is the datasets-server row index.
# --------------------------------------------------------------------------

SPEC = json.loads(r"""[
 {
  "category": "business-economics",
  "register": "literary",
  "subset": "news_filtered",
  "offset": 393,
  "start": "In March 2020, governments around the world",
  "title": "Government debt: you're a part of it. Is it a problem?",
  "author": "Gigi Foster",
  "clean": "lines"
 },
 {
  "category": "business-economics",
  "register": "literary",
  "subset": "news_filtered",
  "offset": 492,
  "start": "When politicians chase popularity",
  "title": "How Sri Lanka sleepwalked over a debt cliff",
  "author": "Umesh Moramudali",
  "clean": "lines"
 },
 {
  "category": "business-economics",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 13707,
  "start": "And now I shall have to go back a bit in my story",
  "title": "Frenzied Finance, vol. 1: \"Standard Oil\" Invests \"Made Dollars\" in Gas",
  "author": "Thomas W. Lawson",
  "clean": "blocks"
 },
 {
  "category": "business-economics",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 1577,
  "start": "So far we have only considered what happens",
  "title": "International Finance: Investments and Securities",
  "author": "Hartley Withers",
  "clean": "blocks"
 },
 {
  "category": "conflict-reporting",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 1540,
  "start": "This story is a personal experience",
  "title": "With the Allies, ch. II: \"To Be Treated As A Spy\"",
  "author": "Richard Harding Davis",
  "clean": "blocks"
 },
 {
  "category": "conflict-reporting",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 9893,
  "start": "Go with the gunners",
  "title": "Impressions of a War Correspondent: A Glimpse of Our Gunners",
  "author": "George Lynch",
  "clean": "blocks"
 },
 {
  "category": "conflict-reporting",
  "register": "literary",
  "subset": "news_filtered",
  "offset": 74921,
  "start": "Agunda Vataeva (LJ user agunya)",
  "title": "Russia: Beslan School Siege Survivor's Account",
  "author": "Veronica Khokhlova",
  "clean": "lines"
 },
 {
  "category": "conflict-reporting",
  "register": "literary",
  "subset": "news_filtered",
  "offset": 94756,
  "start": "Imagine waking up without your bed",
  "title": "Syria's Most Vulnerable Live a Hard Life in Jordan's Refugee Camps",
  "author": "Noon Arabia",
  "clean": "lines"
 },
 {
  "category": "listicle",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:listicle-1",
  "title": "Surprising Benefits of Drinking Warm Lemon Water Every Morning",
  "author": null
 },
 {
  "category": "listicle",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:listicle-2",
  "title": "How to Clean a Cast Iron Skillet: The Ultimate Guide",
  "author": null
 },
 {
  "category": "listicle",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:listicle-3",
  "title": "What Is the Best Time to Visit Portugal?",
  "author": null
 },
 {
  "category": "listicle",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:listicle-4",
  "title": "Why Do Dogs Eat Grass?",
  "author": null
 },
 {
  "category": "criticism",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 6463,
  "start": "Generations of innocents in like manner",
  "title": "Adventures in Criticism: Robinson Crusoe",
  "author": "Arthur Quiller-Couch",
  "clean": "blocks"
 },
 {
  "category": "criticism",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 2320,
  "start": "\"The future of poetry is immense",
  "title": "The Study of Poetry",
  "author": "Matthew Arnold",
  "clean": "blocks"
 },
 {
  "category": "criticism",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 559,
  "start": "The following brief rem",
  "title": "On Criticism (trans. T. Bailey Saunders)",
  "author": "Arthur Schopenhauer",
  "clean": "blocks"
 },
 {
  "category": "criticism",
  "register": "literary",
  "subset": "public_domain_review_filtered",
  "offset": 1199,
  "start": "In October 1856, Herman Melville",
  "title": "The Skeptical Pilgrim: Melville's Clarel",
  "author": "Jeff Wheelwright",
  "clean": "lines"
 },
 {
  "category": "social-post",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:social-post-1",
  "title": "I got rejected from 47 jobs last year",
  "author": null
 },
 {
  "category": "social-post",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:social-post-2",
  "title": "My 6-year-old asked me a question at breakfast",
  "author": null
 },
 {
  "category": "social-post",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:social-post-3",
  "title": "Waitress finds a note under a customer's plate",
  "author": null
 },
 {
  "category": "social-post",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:social-post-4",
  "title": "Unpopular opinion: most meetings should be emails",
  "author": null
 },
 {
  "category": "food-travel",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 2003,
  "start": "William of Malmesbury particularly dwells",
  "title": "Old Cookery Books and Ancient Cuisine: The Early Englishman and His Food",
  "author": "W. Carew Hazlitt",
  "clean": "blocks"
 },
 {
  "category": "food-travel",
  "register": "literary",
  "subset": "public_domain_review_filtered",
  "offset": 1210,
  "start": "Lauded as the “food of the gods”",
  "title": "Pods, Pots, and Potions: Putting Cacao to Paper in Early Modern Europe",
  "author": "Christine Jones",
  "clean": "lines"
 },
 {
  "category": "food-travel",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 153,
  "start": "The captain instantly galloped forward",
  "title": "The Oregon Trail (excerpt)",
  "author": "Francis Parkman",
  "clean": "blocks"
 },
 {
  "category": "food-travel",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 871,
  "start": "Little can be said of the passage from Odessa",
  "title": "A Woman's Journey Round the World: Constantinople (trans.)",
  "author": "Ida Pfeiffer",
  "clean": "blocks"
 },
 {
  "category": "history-writing",
  "register": "literary",
  "subset": "public_domain_review_filtered",
  "offset": 1205,
  "start": "On a hastily built stage",
  "title": "The Dancing Plague of 1518",
  "author": "Ned Pennant-Rea",
  "clean": "lines"
 },
 {
  "category": "history-writing",
  "register": "literary",
  "subset": "public_domain_review_filtered",
  "offset": 1147,
  "start": "The English Channel (la Manche",
  "title": "Liberal Visions and Boring Machines: The Early History of the Channel Tunnel",
  "author": "Peter Keeling",
  "clean": "lines"
 },
 {
  "category": "history-writing",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 2221,
  "start": "The closing quarter of the fifteenth century",
  "title": "Crusaders of New France, ch. I: A Voyageur of Brittany",
  "author": "William Bennett Munro",
  "clean": "blocks"
 },
 {
  "category": "history-writing",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 1668,
  "start": "The result of England's last great colonial struggle",
  "title": "The Winning of the West, vol. 1: The French of the Ohio Valley, 1763-1775",
  "author": "Theodore Roosevelt",
  "clean": "blocks"
 },
 {
  "category": "humor-satire",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 1628,
  "start": "I went often to",
  "title": "A Tramp Abroad, Appendix D: The Awful German Language",
  "author": "Mark Twain",
  "clean": "blocks"
 },
 {
  "category": "humor-satire",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 4189,
  "start": "Well Ethen you will be surprised",
  "title": "A Parody Outline of History: In the Manner of Ring W. Lardner",
  "author": "Donald Ogden Stewart",
  "clean": "blocks"
 },
 {
  "category": "humor-satire",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 965,
  "start": "Rome no doubt did much for England",
  "title": "Comic History of England (excerpt)",
  "author": "Gilbert Abbott à Beckett",
  "clean": "blocks"
 },
 {
  "category": "humor-satire",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 8586,
  "start": "Once every twelve months",
  "title": "Old Fogy Is Pessimistic",
  "author": "James Huneker",
  "clean": "blocks"
 },
 {
  "category": "literary-essay",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 5799,
  "start": "I read the other day some verses",
  "title": "Self-Reliance",
  "author": "Ralph Waldo Emerson",
  "clean": "blocks"
 },
 {
  "category": "literary-essay",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 238,
  "start": "I have an almost feminine partiality for old china",
  "title": "Old China",
  "author": "Charles Lamb",
  "clean": "blocks"
 },
 {
  "category": "literary-essay",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 603,
  "start": "Just now, when every one is bound",
  "title": "An Apology for Idlers",
  "author": "Robert Louis Stevenson",
  "clean": "blocks"
 },
 {
  "category": "literary-essay",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 180,
  "start": "I wish to speak a word for Nature",
  "title": "Walking",
  "author": "Henry David Thoreau",
  "clean": "blocks"
 },
 {
  "category": "literary-essay-more",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 7304,
  "start": "How very delightful Grego's drawings are",
  "title": "Dandies and Dandies",
  "author": "Max Beerbohm",
  "clean": "blocks"
 },
 {
  "category": "literary-essay-more",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 559,
  "start": "A library may",
  "title": "On Thinking for Oneself (trans. T. Bailey Saunders)",
  "author": "Arthur Schopenhauer",
  "clean": "blocks"
 },
 {
  "category": "literary-essay-more",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 3267,
  "start": "One of the pleasant",
  "title": "On Going a Journey (Walking-Stick Papers)",
  "author": "Robert Cortes Holliday",
  "clean": "blocks"
 },
 {
  "category": "literary-essay-more",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 2343,
  "start": "The first of the two great poems commonly ascribed to Homer",
  "title": "The Humour of Homer",
  "author": "Samuel Butler",
  "clean": "blocks"
 },
 {
  "category": "longform-journalism",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 697,
  "start": "Paris remains inactive",
  "title": "Paris under the Commune, ch. V",
  "author": "John Leighton",
  "clean": "blocks"
 },
 {
  "category": "longform-journalism",
  "register": "literary",
  "subset": "news_filtered",
  "offset": 124087,
  "start": "The air over Sesfontein",
  "title": "Strange death of a rhino protector",
  "author": "John Grobler, Oxpeckers Reporters",
  "clean": "lines"
 },
 {
  "category": "longform-journalism",
  "register": "literary",
  "subset": "news_filtered",
  "offset": 113001,
  "start": "A wobbly stroller filled",
  "title": "Scrappers brave the elements trying to make ends meet",
  "author": "Brendan O'Brien",
  "clean": "lines"
 },
 {
  "category": "longform-journalism",
  "register": "literary",
  "subset": "news_filtered",
  "offset": 19207,
  "start": "We drove along the main road",
  "title": "Ghana: Life in a Liberian Refugee Camp",
  "author": "Andy Carvin",
  "clean": "lines"
 },
 {
  "category": "medicine-clinical",
  "register": "literary",
  "subset": "pubmed_filtered",
  "offset": 81428,
  "start": "Pain out of proportion",
  "title": "Rare case of autonomic instability of the lower limb presenting as painless Complex Regional Pain Syndrome type I following hip surgery: two case reports",
  "author": "A. J. Shyam Kumar, S. K. S. Wong, J. G. Andrew",
  "clean": "pmc"
 },
 {
  "category": "medicine-clinical",
  "register": "literary",
  "subset": "pubmed_filtered",
  "offset": 99818,
  "start": "Advancements in diagnostic techniques",
  "title": "Endovascular treatment of thoracoabdominal aortic aneurysm: a case report",
  "author": "Arash Mohammadi Tofigh, Massoud Ghasemi, Babak Heidari Aghdam, Mersedeh Karvandi, Afsoon Kaboli",
  "clean": "pmc"
 },
 {
  "category": "medicine-clinical",
  "register": "literary",
  "subset": "pubmed_filtered",
  "offset": 100176,
  "start": "In the developing world where there is scarcity",
  "title": "Lymphocytic colitis presenting as difficult diarrhoea in an African woman: a case report and review of the literature",
  "author": "Udeme E. Ekrikpo, Jesse A. Otegbayo, Abideen O. Oluwasola",
  "clean": "pmc"
 },
 {
  "category": "medicine-clinical",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 14210,
  "start": "THE POINT AT ISSUE. THE AFFIRMATIVE.",
  "title": "The Contagiousness of Puerperal Fever",
  "author": "Oliver Wendell Holmes",
  "clean": "blocks"
 },
 {
  "category": "memoir-personal",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 8642,
  "start": "Dear son: I have ever had pleasure",
  "title": "Autobiography of Benjamin Franklin (opening)",
  "author": "Benjamin Franklin",
  "clean": "blocks"
 },
 {
  "category": "memoir-personal",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 8550,
  "start": "After having spent two sessions in Edinburgh",
  "title": "The Autobiography of Charles Darwin: Cambridge 1828-1831",
  "author": "Charles Darwin",
  "clean": "blocks"
 },
 {
  "category": "memoir-personal",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 11797,
  "start": "The most important day I remember",
  "title": "The Story of My Life, ch. IV",
  "author": "Helen Keller",
  "clean": "blocks"
 },
 {
  "category": "memoir-personal",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 1689,
  "start": "On the thirtieth day of June, 1897",
  "title": "A Mind That Found Itself, ch. II",
  "author": "Clifford Whittingham Beers",
  "clean": "blocks"
 },
 {
  "category": "music-writing",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 7277,
  "start": "Forty years ago Robert Schumann",
  "title": "Chopin and Other Musical Essays: How Composers Work",
  "author": "Henry T. Finck",
  "clean": "blocks"
 },
 {
  "category": "music-writing",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 4666,
  "start": "Mr. George Frideric Handel is by far",
  "title": "Old Scores and New Readings: Handel",
  "author": "John F. Runciman",
  "clean": "blocks"
 },
 {
  "category": "music-writing",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 8102,
  "start": "Strauss was never the fine",
  "title": "Musical Portraits: Strauss",
  "author": "Paul Rosenfeld",
  "clean": "blocks"
 },
 {
  "category": "music-writing",
  "register": "literary",
  "subset": "public_domain_review_filtered",
  "offset": 1158,
  "start": "Recorded sound began as much",
  "title": "Picturing a Voice: Margaret Watts Hughes and the Eidophone",
  "author": "Rob Mullender-Ross",
  "clean": "lines"
 },
 {
  "category": "nature-place",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 178,
  "start": "By the end of the dry season",
  "title": "The Land of Little Rain: Water Trails of the Ceriso",
  "author": "Mary Austin",
  "clean": "blocks"
 },
 {
  "category": "nature-place",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 13492,
  "start": "The wood thrush is th",
  "title": "Bird Stories from Burroughs: The Wood Thrush",
  "author": "John Burroughs",
  "clean": "blocks"
 },
 {
  "category": "nature-place",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 2808,
  "start": "Lake Tahoe is the largest lake at its altitude",
  "title": "The Lake of the Sky, ch. I: Why \"the Lake of the Sky\"?",
  "author": "George Wharton James",
  "clean": "blocks"
 },
 {
  "category": "nature-place",
  "register": "literary",
  "subset": "public_domain_review_filtered",
  "offset": 1143,
  "start": "21 January 2024: Today I notice",
  "title": "From Snowdrop to Nightjar: Robert Marsham's \"Indications of Spring\"",
  "author": "Hugh Aldersey-Williams",
  "clean": "lines"
 },
 {
  "category": "novel",
  "register": "fiction-draft",
  "subset": "project_gutenberg_filtered",
  "offset": 3032,
  "start": "It is a truth universally acknowledged",
  "title": "Pride and Prejudice, ch. 1-2",
  "author": "Jane Austen",
  "clean": "blocks"
 },
 {
  "category": "novel",
  "register": "fiction-draft",
  "subset": "project_gutenberg_filtered",
  "offset": 3947,
  "start": "Miss Brooke had that kind of beauty",
  "title": "Middlemarch, ch. 1",
  "author": "George Eliot",
  "clean": "blocks"
 },
 {
  "category": "novel",
  "register": "fiction-draft",
  "subset": "project_gutenberg_filtered",
  "offset": 3507,
  "start": "It was four o’clock when the ceremony",
  "title": "The Jungle, ch. 1",
  "author": "Upton Sinclair",
  "clean": "blocks"
 },
 {
  "category": "novel",
  "register": "fiction-draft",
  "subset": "project_gutenberg_filtered",
  "offset": 1376,
  "start": "The towers of Zenith aspired",
  "title": "Babbitt, ch. 1",
  "author": "Sinclair Lewis",
  "clean": "blocks"
 },
 {
  "category": "obituary-eulogy",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 5957,
  "start": "Mr. SPEAKER: I shall leave to others",
  "title": "Memorial Addresses on the Life and Character of William H. F. Lee: Address of Mr. Tucker",
  "author": "Henry St. George Tucker",
  "clean": "blocks"
 },
 {
  "category": "obituary-eulogy",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 7260,
  "start": "It _is_ the day of adversity",
  "title": "Abraham Lincoln: A Memorial Discourse",
  "author": "Thomas Mears Eddy (1823-1874)",
  "clean": "blocks"
 },
 {
  "category": "obituary-eulogy",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 7793,
  "start": "The commemoration which brings us together",
  "title": "Eulogy on Chief-Justice Chase",
  "author": "William M. Evarts",
  "clean": "blocks"
 },
 {
  "category": "obituary-eulogy",
  "register": "literary",
  "subset": "public_domain_review_filtered",
  "offset": 1211,
  "start": "This year brings two notable anniversaries",
  "title": "\"Alas, Poor YORICK!\": The Death and Life of Laurence Sterne",
  "author": "Ian Campbell Ross",
  "clean": "lines"
 },
 {
  "category": "political-essay",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 4125,
  "start": "Mankind being originally equals",
  "title": "Common Sense: Of Monarchy and Hereditary Succession",
  "author": "Thomas Paine",
  "clean": "blocks"
 },
 {
  "category": "political-essay",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 8908,
  "start": "I heartily accept the motto",
  "title": "On the Duty of Civil Disobedience",
  "author": "Henry David Thoreau",
  "clean": "blocks"
 },
 {
  "category": "political-essay",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 13597,
  "start": "What is to be done, what would you have us do?",
  "title": "Past and Present: Morrison's Pill",
  "author": "Thomas Carlyle",
  "clean": "blocks"
 },
 {
  "category": "political-essay",
  "register": "literary",
  "subset": "news_filtered",
  "offset": 98,
  "start": "Australia is considered on the international stage",
  "title": "Australia's world-class democracy has a trust issue",
  "author": "Mark Evans",
  "clean": "lines"
 },
 {
  "category": "press-release",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:press-release-1",
  "title": "Veltrana Systems announces Veltrana Pulse",
  "author": null
 },
 {
  "category": "press-release",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:press-release-2",
  "title": "Northmere Foods partners with Glenharrow Markets",
  "author": null
 },
 {
  "category": "press-release",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:press-release-3",
  "title": "Quorvex raises $42 million in Series B funding",
  "author": null
 },
 {
  "category": "press-release",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:press-release-4",
  "title": "Orbisel Health appoints Karen Whitfield as Chief Operating Officer",
  "author": null
 },
 {
  "category": "profile-writing",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 12138,
  "start": "Hawthorne was an excellent critic",
  "title": "Four Americans: Fifty Years of Hawthorne",
  "author": "Thomas Wentworth Higginson",
  "clean": "blocks"
 },
 {
  "category": "profile-writing",
  "register": "literary",
  "subset": "public_domain_review_filtered",
  "offset": 1194,
  "start": "In May 1884, long before",
  "title": "\"I Am My Own Heroine\": How Marie Bashkirtseff Rewrote the Route to Fame",
  "author": "Sonia Wilson",
  "clean": "lines"
 },
 {
  "category": "profile-writing",
  "register": "literary",
  "subset": "public_domain_review_filtered",
  "offset": 1191,
  "start": "Dorothy Parker lost her job",
  "title": "When Dorothy Parker Got Fired from Vanity Fair",
  "author": "Jonathan Goldman",
  "clean": "lines"
 },
 {
  "category": "profile-writing",
  "register": "literary",
  "subset": "news_filtered",
  "offset": 98162,
  "start": "Rony Marton may not be a well-known name",
  "title": "From Indonesian exile to Czechoslovakian pop star: An interview with Rony Marton",
  "author": "Juke Carolina",
  "clean": "lines"
 },
 {
  "category": "corporate-blog",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:corporate-blog-1",
  "title": "The future of work is aligned",
  "author": null
 },
 {
  "category": "corporate-blog",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:corporate-blog-2",
  "title": "AI readiness comes before AI tools",
  "author": null
 },
 {
  "category": "corporate-blog",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:corporate-blog-3",
  "title": "Customer success is dead. Long live customer outcomes.",
  "author": null
 },
 {
  "category": "corporate-blog",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:corporate-blog-4",
  "title": "Why the best engineering teams are rethinking developer productivity",
  "author": null
 },
 {
  "category": "science-nature",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 64,
  "start": "If a well were sunk at our feet",
  "title": "On a Piece of Chalk",
  "author": "Thomas Henry Huxley",
  "clean": "blocks"
 },
 {
  "category": "science-nature",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 3919,
  "start": "I purpose, in return for the honour",
  "title": "The Chemical History of a Candle, Lecture I",
  "author": "Michael Faraday",
  "clean": "blocks"
 },
 {
  "category": "science-nature",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 306,
  "start": "Ladies and gentlemen, we may of course think",
  "title": "Thoughts in a Gravel-Pit",
  "author": "Charles Kingsley",
  "clean": "blocks"
 },
 {
  "category": "science-nature",
  "register": "literary",
  "subset": "news_filtered",
  "offset": 12,
  "start": "At the Institute for Marine and Antarctic Studies",
  "title": "A new wave of research in the Southern Ocean",
  "author": "Helen Phillips",
  "clean": "lines"
 },
 {
  "category": "seo-article",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:seo-article-1",
  "title": "The best project management software for small business",
  "author": null
 },
 {
  "category": "seo-article",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:seo-article-2",
  "title": "Email marketing best practices",
  "author": null
 },
 {
  "category": "seo-article",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:seo-article-3",
  "title": "How much does a kitchen remodel cost?",
  "author": null
 },
 {
  "category": "seo-article",
  "register": "commercial",
  "subset": "synthetic",
  "source": "synthetic:seo-article-4",
  "title": "The ultimate beginner's guide to SEO",
  "author": null
 },
 {
  "category": "speech-rhetoric",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 291,
  "start": "I am certain that on this",
  "title": "First Inaugural Address (1933)",
  "author": "Franklin Delano Roosevelt",
  "clean": "blocks"
 },
 {
  "category": "speech-rhetoric",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 3740,
  "start": "Fellow-countrymen: At this second appearing",
  "title": "Second Inaugural Address (1865)",
  "author": "Abraham Lincoln",
  "clean": "blocks"
 },
 {
  "category": "speech-rhetoric",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 2300,
  "start": "This uncounted multitude",
  "title": "The Bunker Hill Monument (1825)",
  "author": "Daniel Webster",
  "clean": "blocks"
 },
 {
  "category": "speech-rhetoric",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 377,
  "start": "My fellow citizens, today we celebrate",
  "title": "Inaugural Address (1993)",
  "author": "William J. Clinton",
  "clean": "blocks"
 },
 {
  "category": "sports-writing",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 6887,
  "start": "I had looked forward all the year to our playing Cornell",
  "title": "Football Days: Memories of the Game",
  "author": "William H. Edwards",
  "clean": "blocks"
 },
 {
  "category": "sports-writing",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 33,
  "start": "Not for some time has there been such a turning over",
  "title": "Spalding's Official Baseball Guide 1913 (article)",
  "author": "John B. Foster",
  "clean": "blocks"
 },
 {
  "category": "sports-writing",
  "register": "literary",
  "subset": "public_domain_review_filtered",
  "offset": 1200,
  "start": "The oldest film included on the National Film Registry",
  "title": "Eastern Sports and Western Bodies: The \"Indian Club\" in the United States",
  "author": "Daniel Elkind",
  "clean": "lines"
 },
 {
  "category": "sports-writing",
  "register": "literary",
  "subset": "news_filtered",
  "offset": 89614,
  "start": "On March 27th, the West Indies Cricket Board",
  "title": "What will New WICB President bring to West Indies Cricket?",
  "author": "Matthew Hunte",
  "clean": "lines"
 },
 {
  "category": "technical-craft",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 8633,
  "start": "The cutting of a line block needs patience",
  "title": "Wood-Block Printing: Cutting the Line Block",
  "author": "F. Morley Fletcher",
  "clean": "blocks"
 },
 {
  "category": "technical-craft",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 13963,
  "start": "The leaves of a vellum book that have become cockled",
  "title": "Bookbinding, and the Care of Books: Flattening Vellum",
  "author": "Douglas Cockerell",
  "clean": "blocks"
 },
 {
  "category": "technical-craft",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 14104,
  "start": "Having procured a piece of sycamore",
  "title": "The Repairing & Restoration of Violins (excerpt)",
  "author": "Horace Petherick",
  "clean": "blocks"
 },
 {
  "category": "technical-craft",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 700,
  "start": "As no two people, probably, ever did",
  "title": "Play-Making: The Routine of Composition",
  "author": "William Archer",
  "clean": "blocks"
 },
 {
  "category": "technical-craft-more",
  "register": "literary",
  "subset": "python_enhancement_proposals_filtered",
  "offset": 652,
  "start": "In numerical code, there are two important operations",
  "title": "PEP 465: A dedicated infix operator for matrix multiplication",
  "author": "Nathaniel J. Smith",
  "clean": "md"
 },
 {
  "category": "technical-craft-more",
  "register": "literary",
  "subset": "python_enhancement_proposals_filtered",
  "offset": 274,
  "start": "This PEP provides the motivation and rationale",
  "title": "PEP 635: Structural Pattern Matching: Motivation and Rationale",
  "author": "Tobias Kohn, Guido van Rossum",
  "clean": "md"
 },
 {
  "category": "technical-craft-more",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 4980,
  "start": "METHODS OF TREATMENT. After choosing a subject",
  "title": "How to Write Special Feature Articles: Types of Articles",
  "author": "Willard Grosvenor Bleyer",
  "clean": "blocks"
 },
 {
  "category": "technical-craft-more",
  "register": "literary",
  "subset": "project_gutenberg_filtered",
  "offset": 992,
  "start": "What constitutes a good fireman?",
  "title": "Rough and Tumble Engineering: A Good Fireman",
  "author": "James H. Maggard",
  "clean": "blocks"
 }
]""")
if os.environ.get("PW_SPEC"):
    SPEC = json.loads(pathlib.Path(os.environ["PW_SPEC"]).read_text())


def write_licenses(manifest):
    lines = [
        "# Licenses and attribution",
        "",
        "Every text in `texts/` is public domain, CC0 1.0, CC BY 4.0, CC BY-SA 3.0 or CC BY-SA 4.0.",
        "No text is under a NonCommercial (NC) or NoDerivatives (ND) license.",
        "",
        "All texts are **excerpts** of the original works and have been **reformatted**: markup,",
        "headings, captions, footnote markers, citations, block quotations and reference lists were",
        "removed, hard-wrapped lines were joined, and each text was cut to whole paragraphs of roughly",
        "300 to 900 words (an over-long final paragraph is cut at a sentence boundary). The wording",
        "of what remains is unchanged. Each license is the one recorded in the document's",
        "Common Pile v0.1 row metadata, https://huggingface.co/common-pile (Public Domain Review",
        "items: as stated by the publisher).",
        "",
        "## No attribution required",
        "",
        "- **Public domain** items (Project Gutenberg books from `common-pile/project_gutenberg_filtered`,",
        "  and Python Enhancement Proposals, which their authors placed in the public domain) and",
        "  **CC0** items need no attribution. Project Gutenberg texts are public domain in the United",
        "  States; their status in other countries may differ. Gutenberg license boilerplate is not included.",
        "- **Synthetic** items (`source_dataset: synthetic`) were generated with an LLM for this corpus",
        "  and are dedicated to the public domain under CC0 1.0. Every company, product and person",
        "  named in them is fictional.",
        "",
        "## CC BY and CC BY-SA attributions",
        "",
        "The excerpted and reformatted CC BY-SA items are adaptations and remain under the CC BY-SA",
        "version stated for each (3.0 or 4.0).",
        "",
    ]
    for m in manifest:
        lic = m["license"]
        if lic in ("CC-BY-4.0", "CC-BY-SA-3.0", "CC-BY-SA-4.0"):
            if m.get("license_note"):
                stated = f"{LICENSE_NAMES.get(lic, lic)} ({LICENSE_URLS[lic]}), as stated by the publisher"
            else:
                stated = f"{lic} ({LICENSE_URLS[lic]})"
            lines.append(
                f"- `{m['file']}`: \"{m['title']}\" by {m['author'] or 'unknown'}. "
                f"Source: {m['source_url_or_id']} (via {m['source_dataset']}). "
                f"License: {stated}. Excerpted and reformatted."
            )
    (HERE / "LICENSES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = sys.argv[1:]
    if "--only" in args:
        k = int(args[args.index("--only") + 1])
        e = SPEC[k]
        txt, n, row = build_one(e)
        print(txt)
        print(f"[{k}] {e['category']} words={n}", file=sys.stderr)
        return
    check = "--check" in args
    old = {}
    if (HERE / "manifest.json").exists():
        old = {m["file"]: m["sha256"] for m in json.loads((HERE / "manifest.json").read_text())}
    TEXTS.mkdir(exist_ok=True)
    manifest, bad = [], 0
    for k, e in enumerate(SPEC):
        name = f"texts/{k:03d}.txt"
        f = HERE / name
        if e["subset"] == "synthetic":
            txt = f.read_text(encoding="utf-8")       # authored text, kept as is
            n = len(txt.split())
            lic, src, ds = "CC0-1.0", e["source"], "synthetic"
        else:
            txt, n, row = build_one(e)
            lic, src, ds = license_of(row), source_of(row), f"common-pile/{e['subset']}"
            lic, note = PUBLISHER_LICENSE.get(e["subset"], (lic, None))
            if not check:
                f.write_text(txt, encoding="utf-8")
        sha = hashlib.sha256(txt.encode("utf-8")).hexdigest()
        if check and old.get(name) != sha:
            print("MISMATCH", name, e["title"])
            bad += 1
        rec = {"file": name, "category": e["category"], "register": e["register"], "title": e["title"],
               "author": e.get("author"), "source_dataset": ds, "source_url_or_id": src,
               "license": lic, "words": n, "sha256": sha}
        if ds != "synthetic":
            rec["common_pile_row"] = e["offset"]
            if note:
                rec["license_note"] = note
        manifest.append(rec)
        if not 300 <= n <= 1035:
            print("LENGTH", name, n, e["title"])
    if not check:
        (HERE / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        write_licenses(manifest)
    print(f"{len(manifest)} texts, {bad} hash mismatches")


if __name__ == "__main__":
    main()
