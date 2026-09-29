#!/usr/bin/env python3
"""BUILD TIME ONLY (needs spaCy + en_core_web_sm): spaCy en_core_web_sm (MIT) annotations of open-licensed
web news and magazine text, for training the sentence segmenter on the kind of text
proseweave sees (headings, lists, captions, blank-line paragraphs).

Inputs, in RAW_DIR (tools/build_mag_news_freq.py `download` fetches them):
news_filtered.json.gz (Common Pile, CC BY articles only are used), foodista.json.gz
(CC BY 3.0) and wikinews_en.parquet (CC BY 2.5). Needs spaCy + en_core_web_sm and
pyarrow. Line breaks become blank-line paragraph breaks.
Output: one JSON line per document, same layout as tools/syntax/dump_spacy.py:
{"id", "toks": [[text, ws, tag, pos, head, sent_start], ...]}

    python dump_news.py RAW_DIR OUT.jsonl MAX_TOKENS
"""
import gzip, json, random, sys
import spacy


def main():
    RAW, out_path, max_tokens = sys.argv[1], sys.argv[2], int(sys.argv[3])
    docs = []
    for line in gzip.open(f"{RAW}/news_filtered.json.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        lic = d["metadata"].get("license", "")
        if "Attribution" in lic and "Share-Alike" not in lic:
            docs.append(("news/" + d["id"], d["text"]))
    for line in gzip.open(f"{RAW}/foodista.json.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        docs.append(("foodista/" + d["id"], d["text"]))
    import pyarrow.parquet as pq
    for r in pq.read_table(f"{RAW}/wikinews_en.parquet", columns=["title", "text"]).to_pylist():
        if ":" not in (r["title"] or "").split(" ")[0]:
            t = r["text"] or ""
            for c in ("Have an opinion on this story?", "Share this:", "This page is archived"):
                i = t.find(c)
                if i >= 0:
                    t = t[:i]
            docs.append(("wikinews/" + r["title"], t))
    random.Random(11).shuffle(docs)
    picked, n = [], 0
    for i, t in docs:
        t = "\n\n".join(p.strip() for p in t.split("\n") if p.strip())[:20000]
        if len(t) < 400:
            continue
        picked.append((i, t))
        n += len(t.split())
        if n >= max_tokens:
            break
    nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
    with open(out_path, "w") as out:
        for (i, _), doc in zip(picked, nlp.pipe((t for _, t in picked), batch_size=32, n_process=8)):
            toks = [[t.text, t.whitespace_, t.tag_, t.pos_, t.head.i, int(t.is_sent_start or t.i == 0)] for t in doc]
            out.write(json.dumps({"id": i, "toks": toks}) + "\n")
    print(len(picked), "docs,", n, "words")


if __name__ == "__main__":
    main()
