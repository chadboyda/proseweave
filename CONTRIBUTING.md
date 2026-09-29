# Contributing

Thank you for helping. proseweave has three rules that matter more than style.

## 1. No copying

proseweave follows the published definitions of each index and is scored
against reference outputs (TAACO 2.0, a spaCy-based feature script and an LLM
judge; see `validation/PROTOCOL.md`). It must never contain those tools' code,
word lists or data files, and it must not be rebuilt from them.

- Don't paste, translate or closely paraphrase code from another text-analysis
  tool, whatever its licence.
- Don't consult another tool's word lists or data files when writing or
  changing proseweave's own (for example `data/connectives_en.json`). Don't
  tune a list item by item against a reference tool's outputs either.
- Build data files only from inputs under open licences (public domain, CC0,
  MIT/BSD/Apache, PDDL/ODC-BY, CC BY, CC BY-SA). Record the source and licence
  in `NOTICE` and in the file's own notice under `src/proseweave/data/`.
- Formulas and definitions from the published literature are fine: cite them.

## 2. Standard library only at run time

`src/proseweave` imports nothing outside the Python standard library (3.9+)
and downloads nothing. Build scripts in `tools/` may use anything, as long as
their output is a data file. Keep the bundled data under 25 MB in total.

## 3. The validation protocol

A change that moves any property's values needs numbers.
[validation/PROTOCOL.md](validation/PROTOCOL.md) fixes the pass mark:
Spearman rho >= 0.80 and a bootstrap 90% lower bound >= 0.70, on both
validation corpora.

- If you tune anything (wordings, weights, thresholds, feature choices), tune
  on the even-numbered texts and report on the odd-numbered ones.
- Report before and after for every property you touch, on both corpora, and
  show that no passing property falls below the bar.
- The open corpus (`validation/open/`) ships in full. The article corpus ships
  as a manifest with proseweave's values (`validation/articles/`). `rebuild.py`
  refetches it approximately.

Reference outputs are not redistributed. To score a run, generate your own
reference values by running the reference tools on the corpus texts (the open
texts are in `validation/open/texts/`; the article texts rebuild with
`validation/articles/rebuild.py`), save them as `{text id: {property: value}}`,
for example `my_reference.json`, and pass that file to `score.py`:

```sh
python3 validation/score.py my_reference.json validation/open/proseweave.json
```

## Rebuilding the data files

Each data file names its build script in `NOTICE`:

| file | script |
|---|---|
| `syntax_en.bin.gz` | `tools/syntax/` (fetch_text, dump_spacy, train, train_seg2, repack, pack_binary) |
| `mag_news_freq.bin.xz` | `tools/build_mag_news_freq.py` (download, tag, count, pack) |
| `zipf_en.bin.gz` | `tools/build_zipf_table.py` (then `tools/pack_tables.py`) |
| `syllables_en.bin.gz` | `tools/build_syllables.py` (then `tools/pack_tables.py`) |
| `validation/open/texts` | `validation/open/build_open_corpus.py` |

Build scripts run once, offline apart from fetching their open inputs, and
write a data file. Commit the script alongside the data file it produces.

## Tests

```sh
python -m unittest discover -s tests      # offline; no key needed
PROSEWEAVE_SLOW=1 python -m unittest discover -s tests   # also the README table check
```

CI runs the offline suite on Python 3.9-3.13. Tests must not call Jev: mock
`urllib.request.urlopen`, or use a cache directory.

## Wording

Describe proseweave as inspired by and building on the published research.
In docs, comments and commit messages, don't describe it as a copy or version
of another tool, and don't discuss other tools' internals or defects.
