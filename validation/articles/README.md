# Article corpus

108 texts across 27 kinds of writing, in literary and commercial registers:
104 excerpts of published articles, and 4 chapters of the author's own
unpublished fiction.

The texts themselves are not distributed, because the articles are
copyrighted. This folder holds only what was derived from them:

| file | what it is |
|---|---|
| `manifest.json` | each text's source URL, category, register, word count and the SHA-256 of the exact excerpt measured |
| `proseweave.json` | proseweave's values per text and property |
| `proseweave_source_pairs.json` | proseweave's values for the 60 source/rewrite pairs |
| `rebuild.py` | fetches each URL, extracts the body text and cuts the same excerpt |

## Checking the results

The reference outputs are not redistributed. To reproduce the published
scores, rebuild the texts (below), generate your own reference values by
running the reference tools on them, save those as `{text id: {property:
value}}` (for example `my_reference.json`), and pass that file to `score.py`:

```bash
python3 ../score.py my_reference.json proseweave.json
python3 ../score.py my_reference_source_pairs.json proseweave_source_pairs.json
```

## Rerunning on the texts

`python3 rebuild.py OUT_DIR` rebuilds the corpus from its sources. A rebuilt
excerpt rarely matches the measured one byte for byte, because pages change
and text extractors differ.

In a test rebuild:
- 99 of the 104 pages were reachable.
- The median rebuilt text shared 95% of its word sequence with the original.
- Basic measures on rebuilt and original texts correlated at 0.79-0.94.

So a reference generated on a rebuilt corpus will not match the published
numbers exactly; use it to try out changes. For a corpus that ships in full,
see `../open/`.
