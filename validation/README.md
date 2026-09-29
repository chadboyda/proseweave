# validation/

How proseweave's properties were checked, and the results.

- `PROTOCOL.md`: the rule and the pass mark, fixed before any results were seen.
- `RESULTS.md`: per-property results for the 202 single-text properties on
  both corpora. It is generated from `src/proseweave/data/validation.json` by
  `tools/results_table.py`.
- `RESULTS_PAIRS.md`: the 26 source-comparison properties.
- `score.py`: scores any pair of value files (standard library only).
- `catalog.py`: every single-text property with its family and a plain-words
  question.
- `judge_retest.json`: test-retest figures for the LLM judge that is the
  reference for the six judge-scale properties (numbers only).
- `articles/`: the article corpus, 108 texts. The texts are copyrighted, so
  this folder ships only their manifest (URL, category and hash per text),
  proseweave's values and a rebuild script. See `articles/README.md`.
- `open/`: the open corpus, 108 texts under public-domain, CC0, CC BY and
  CC BY-SA terms. The texts ship in full, with attribution in
  `open/LICENSES.md`, and `build_open_corpus.py` rebuilds them.

A property counts as validated only if it passes on both corpora. Each
property's rho and lower bound on each corpus, and whether it is valid, ship
in `src/proseweave/data/validation.json`, which `profile` and `compare` read.

The six judge-scale properties (narrativity, word_concreteness,
syntactic_simplicity, referential_cohesion, deep_cohesion, overall_quality)
have an LLM judge as their reference. A single run of that judge repeats at
rho 0.77-0.98 depending on the property (0.77-0.83 for the three cohesion and
quality scores), so these properties are validated against the mean of 10
judge runs on the article corpus and 6 on the open corpus, whose reliability
is 0.94-1.00. `judge_retest.json` gives the per-property figures for both
corpora: agreement between single runs, split-half agreement and the
reliability of the mean.

## Checking the published numbers

The reference outputs are not redistributed: this folder ships proseweave's
values (`*/proseweave.json`, `*/proseweave_source_pairs.json`) but not the
values the reference tools produced. To reproduce the published numbers,
generate your own reference values by running the reference tools on the
corpus texts. The open texts are in `open/texts/`; the article texts rebuild
with `articles/rebuild.py`. Save the reference values as
`{text id: {property: value}}`, keyed like proseweave's file (pair ids for the
source pairs), for example as `my_reference.json`, and pass that file to
`score.py`:

```sh
python3 score.py articles/my_reference.json articles/proseweave.json
python3 score.py articles/my_reference_source_pairs.json articles/proseweave_source_pairs.json
python3 score.py open/my_reference.json open/proseweave.json
python3 score.py open/my_reference_source_pairs.json open/proseweave_source_pairs.json
```

## Rerunning the comparison

You can repeat the check on your own texts. Run the tools you want to compare
against on those texts, then run proseweave on the same texts:

```python
from proseweave import Analysis, Jev
j = Jev()
ours = {name: Analysis(text, j).properties() for name, text in texts.items()}
```

Save both as `{text id: {property: value}}` and pass the two files to
`score.py`. Setting `PROSEWEAVE_CACHE` to a directory makes reruns free.

## Why semantic_cohesion std, min and max stay below the bar

The sentence-similarity indices (`semantic_cohesion_*`, `paragraph_cohesion_*`)
are defined by a transformer sentence-embedding model (all-MiniLM-L6-v2).
proseweave approximates that model with a static table: one vector per
WordPiece token, trained so that cosines between summed token vectors match the
model's cosines on public-domain text. For each pair of adjacent sentences, a
stored blend then combines that table's cosine with a GloVe cosine and, where
Jev is available, Jev's rating of the pair. This is good enough for the
mean-based indices (semantic_cohesion_mean, paragraph_cohesion_mean and _std
all pass). The spread statistics need more. They depend on individual sentence
pairs, and the lowest and highest pairs in a text are exactly where a static
model's errors concentrate.

We measured how accurate each pair would need to be by feeding in the
reference model's own cosines with controlled noise. std needs a per-pair
correlation of about 0.90 with the reference, and max about 0.95. min fails
even with exact cosines (held-out rho 0.82, lower bound 0.65), because the
standard-library sentence splitter cannot reproduce the reference's splits
exactly. The static table's per-pair correlation grows slowly with training
data:

| training sentences (public domain) | per-pair r |
|---|---|
| 1.5M | 0.748 |
| 2.3M | 0.770 |
| 3.5M | 0.790 |
| 6.5M | 0.804 |
| 16.6M | 0.819 (0.843 with Jev) |

Each doubling now adds about 0.012. Reaching r 0.90 would take on the order of
100 times more text, or a contextual model that cannot run in the standard
library within the speed budget. At the shipped size, semantic_cohesion_std
reaches rho 0.77 (lower bound 0.67) on the article corpus and 0.78 (0.70) on
the open corpus. These three indices are reported, but they are marked below
the bar.
