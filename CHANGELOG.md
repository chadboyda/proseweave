# Changelog

All notable changes to proseweave. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Output property names are part of
the public interface: renaming or removing one is a breaking change.

## [0.2.0] - unreleased

First public release.

### Properties
- 230 named properties: 202 single-text properties, two construct scores
  (`referential_cohesion_construct`, `deep_cohesion_construct`) and 26
  source-comparison properties.
- Lexical and readability measures (counts, type-token ratio, MTLD, sentence
  length, Flesch reading ease, Flesch-Kincaid grade, automated readability
  index, word frequency and familiarity), word-class ratios and dependency
  distance.
- 168 cohesion indices: overlap, lexical diversity, connectives, givenness,
  synonyms and segment similarity, plus semantic and paragraph cohesion.
- Easability components (narrativity, word concreteness, syntactic
  simplicity, referential cohesion, deep cohesion) and an overall quality
  score.
- Source comparison: whole-text similarity, and how much of a rewrite is made
  of its source's keywords and key n-grams.

### Cadence and rhythm
- `proseweave cadence` and `cadence.measure()`: sentence and paragraph rhythm
  in reading order, as numbers only. Stress beat (clashes, alternation,
  lapses, stressed endings), phrase contrast and end weight, paragraph landing
  and the sentence-length contour, each order-dependent statistic reported
  against 20 seeded shuffles of the same text.
- Pattern spans (flat stretches, runs of long or short sentences, repeated
  structure, unconnected runs, dense relations, emphasis points, paragraph
  rhythm) against the document's own percentiles.
- `cadence.align()`: pairs the paragraphs of two versions of a text,
  including splits, merges and changes of content type.
- Local only: no key and no network.

### Validation
- Rank agreement with reference outputs on two 108-text corpora: an article
  corpus (texts not redistributed) and an open-licensed corpus that ships in
  full. Pass mark: Spearman rho >= 0.80 and a bootstrap 90% lower bound
  >= 0.70.
- Single-text properties: 195 of 202 pass on the article corpus and 189 on
  the open corpus; 189 pass on both and count as validated.
- Source-comparison properties (60 pairs per corpus): 17 of 26 pass on the
  article corpus and 20 on the open corpus; 15 pass on both.
- Per-property results ship in `data/validation.json`; properties below the
  bar are still computed but flagged and excluded from `profile` and
  `compare`.

### No-key mode
- `--no-jev` or `Analysis(text, None)` gives 197 of the 202 single-text
  properties and both construct scores, with no key and no network; 184 of
  them pass on both corpora.
- If Jev becomes unavailable mid-run, proseweave prints a one-line warning and
  returns the same no-key set.

### Also
- Pure Python standard library, no dependencies: a bundled tagger, sentence
  segmenter and dependency parser, and open-licensed frequency, word-vector,
  syllable and synonym tables (sources and licences in NOTICE).
- Optional Jev judgements (TypeSafe) for low-confidence word classes,
  relatedness, familiarity and the judgement-scale properties, with an answer
  cache (`PROSEWEAVE_CACHE`).
- CLI: `proseweave TEXT`, `profile`, `compare`, `source`, `cadence`, `setup`,
  `check`.
