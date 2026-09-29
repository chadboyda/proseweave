# proseweave

Measures how a piece of prose holds together: vocabulary, readability, word
classes, cohesion between sentences and paragraphs, easability, and how a
rewrite relates to its source. Pure Python standard library, no dependencies.

Word classes, dependency heads, word vectors and reference frequencies come
from small bundled data files. The judgements they cannot settle (a word the
tagger is unsure of, how related two passages are, how familiar a word is)
are asked of TypeSafe's Jev model over HTTPS. Everything else is arithmetic in
this package.

## What it measures

About 230 named properties, in these groups:

- **Lexical and readability**: token and type counts, type-token ratio, MTLD,
  sentence length (mean, spread, variation), Flesch reading ease,
  Flesch-Kincaid grade, automated readability index, word familiarity.
- **Word classes**: noun, verb, adjective and adverb ratios, and dependency
  distance.
- **Cohesion**
  - *overlap*: how much each sentence or paragraph repeats words, content
    words, nouns, pronouns and so on from the next one or two
    (`adjacent_overlap_*`), and lexical diversity by word class (`*_ttr`,
    `*_mattr`);
  - *connectives*: additive, causal, temporal, adversative and other
    connectives, determiners and demonstratives, per word;
  - *givenness*: pronoun density and repeated content words;
  - *synonyms*: overlap through WordNet synonyms between adjacent segments;
  - *semantic similarity*: how close in meaning neighbouring sentences and
    paragraphs are. `lda_*` indices keep the published names but are
    computed from the bundled vector spaces, not a topic model.
- **Easability**: narrativity, word concreteness, syntactic simplicity,
  referential cohesion, deep cohesion, and an overall quality score, 0-100.
- **Comparing a text with its source**: whole-text similarity, and how much of
  the target is made of the source's keywords and key n-grams.

Output property names (for example `adjacent_overlap_cw_sent`) are stable.

Separately from the properties, **cadence measurements** record sentence and
paragraph rhythm in reading order (see [Cadence measurements](#cadence-measurements)).

## Quick start

```sh
pip install -e .
proseweave setup                      # store a Jev API key
proseweave essay.txt                  # every property of one text
proseweave essay.txt --json
proseweave essay.txt --no-jev         # no key needed; most properties
proseweave profile mine/*.txt --out me.json
proseweave compare draft.txt --baseline me.json
proseweave source original.txt rewrite.txt
proseweave cadence essay.txt --json   # cadence measurements; no key needed
proseweave check                      # is a working key set?
```

`profile` records the range each property takes over an author's samples;
`compare` lists where a draft falls outside it, strongest first. They point at
passages to reread; they are not targets. `compare` exits 0 when nothing is
outside the range, 1 when something is, 2 on a missing key or usage error.

From Python:

```python
from proseweave import Analysis, Jev, profile, compare, compare_source

j = Jev()
props = Analysis(text, j).properties()      # dict of property -> value
basic = Analysis(text, None).basic()        # no key needed
prof = profile([sample1, sample2, sample3], j)
flags = compare(draft, prof, j)
src = compare_source(original, rewrite, j)
```

## Cadence measurements

`proseweave cadence` measures the rhythm of a text in reading order, as
numbers for building diagnostics: no text, no interpretation, no score, and no
ideal sentence length, ratio or pattern. It is local (no key, no network) and
not part of `properties()`.

```sh
proseweave cadence chapter.txt          # a summary
proseweave cadence chapter.txt --json   # every measurement, compact JSON (about 7 KB for 1,000 words)
```

```python
from proseweave import cadence
m = cadence.measure(text)            # summary, sentences, paragraphs, phrases, patterns, rhythm
a = cadence.align(before, after)     # aligned passages of two versions
```

- **Sentences and paragraphs** are columns (equal-length lists per field):
  character offsets, words, syllables, stresses, syllables after the last
  stress, phrase lengths, pauses, relation markers, overlap with and
  similarity to the previous sentence, paragraph position. Content types are
  codes: 0 prose, 1 heading, 2 list item, 3 quotation, 4 code, 5 table; only
  prose enters the statistics.
- **Rhythm**, in syllables, at three levels:
  - *beat*: the stream of stressed syllables (CMUdict stress for words of two
    or more syllables, word class for monosyllables): the share of stress
    clashes, of alternating intervals (two or three syllables) and of lapses
    (three or more unstressed in a row), and how often sentences end on a stress;
  - *phrase*: phrases split at `, ; :`, dashes and parentheses: the contrast
    between neighbouring phrases (nPVI), and the weight of the final phrase;
  - *landing*: each paragraph's first and last sentence against its median;
  - and the contour: a moving mean and coefficient of variation of sentence
    length, and its lag-1 autocorrelation.

  Every statistic that depends on order is reported with its value over 20
  shuffles of the same text (fixed seed) and a z against them. On the open
  corpus the beat is where order matters: stress clashes run below the
  shuffled rate in 84% of texts. Sentence-length order mostly does not.
- **Patterns** locate passages as spans with their numbers, against the
  document's own percentiles: flat stretches, runs of long or short
  sentences, repeated structure against repeated terminology, unconnected
  runs of short sentences, sentences dense with relations, emphasis points and
  paragraph rhythm.
- **Alignment** pairs the paragraphs of two versions by their content words,
  allowing splits, merges and changes of content type, as columns of spans and
  status codes.

## Jev

Jev is TypeSafe's typed-question model. You need a TypeSafe API key
(https://console.typesafe.ai). `proseweave setup` stores it in
`~/.config/proseweave/credentials` (mode 600); `TYPESAFE_API_KEY` in the
environment or a `.env` file also works. Measured on the two validation
corpora, uncached, a document costs about $0.004 of Jev per 1,000 words,
source comparison included. Set `PROSEWEAVE_CACHE` to a directory to cache
answers, so a rerun on the same text makes no requests.

With no key (`--no-jev`, or `Analysis(text, None)`), you get 197 of the 202
single-text properties, plus the two construct properties. Word classes come
from the bundled tagger alone, dependency distance from the bundled parser,
word frequency from the bundled table, and semantic similarity from the bundled
word vectors without Jev's ratings. That covers the lexical and readability
counts, word frequency (`zipf_*`), word-class ratios, dependency distance,
every cohesion index (overlap, lexical diversity, connectives, givenness,
synonyms, segment similarity), semantic and paragraph cohesion, and
`syntactic_simplicity`. The judge-scale easability components need a key, as
does `proseweave source`. Without a key, 184 properties pass on both validation
corpora; the sentence-level semantic cohesion indices lose the most. If Jev
becomes unavailable mid-run (no credits, a rejected key, no network),
proseweave prints a one-line warning and returns this same no-key set;
`proseweave source` falls back to the frequency tables alone.

## Validation

Each property was checked for rank agreement with reference outputs: TAACO 2.0
for the cohesion and source indices, a spaCy-based feature script for the basic
features, and an LLM judge for the easability components (run by us; not
redistributed). There are two corpora of 108 texts each, in literary and
commercial registers: an article corpus (texts not redistributed), and an
open-licensed corpus that anyone can rebuild. The pass mark, fixed in advance:
Spearman rho of at least 0.80 and a bootstrap 90% lower bound of at least 0.70.

| | article corpus | open corpus |
|---|---|---|
| single-text properties | 195 of 202 | 189 of 202 |
| source properties (60 pairs) | 17 of 26 | 20 of 26 |

A property counts as validated only if it passes on both corpora: 189 of the
202 single-text properties do. Jev's answers can vary slightly from run to
run; the published numbers come from a cached, reproducible run. The six
judge-scale easability properties are scored against the mean of repeated runs
of their LLM-judge reference (10 on the article corpus, 6 on the open one),
since a single run of the judge does not repeat reliably enough to be a target;
see `validation/judge_retest.json`. See [validation/](validation/) for the
protocol, per-property results and how to rerun the comparison with your own
reference outputs.

Two more properties, `referential_cohesion_construct` and
`deep_cohesion_construct`, are defined by the published formula (Graesser,
McNamara & Kulikowich 2011) over validated indices; they have no external
reference, so they are not counted above.

Properties below the bar are still computed, but they are flagged in
`src/proseweave/data/validation.json` (which records rho and the lower bound
on each corpus) and excluded from `profile` and `compare`.

## Acknowledgements

proseweave is heavily inspired by, and builds on, decades of published research
on text cohesion and readability, above all the work behind TAACO and
Coh-Metrix. Its indices follow the definitions in the papers below, and its
outputs were scored against reference outputs to check that each measures
what it is meant to (see Validation). It contains none of their code, word
lists or data files.

Property names follow the index names used in the TAACO publications, so
results can be compared side by side; every computation, word list and data
file is proseweave's own.

proseweave is independent and not affiliated with or endorsed by the authors of these tools.

- Crossley, S. A., Kyle, K., & McNamara, D. S. (2016). The tool for the
  automatic analysis of text cohesion (TAACO): Automatic assessment of local,
  global, and text cohesion. *Behavior Research Methods*, 48(4), 1227-1237.
- Crossley, S. A., Kyle, K., & Dascalu, M. (2019). The Tool for the Automatic
  Analysis of Cohesion 2.0: Integrating semantic similarity and text overlap.
  *Behavior Research Methods*, 51(1), 14-27.
- McNamara, D. S., Graesser, A. C., McCarthy, P. M., & Cai, Z. (2014).
  *Automated Evaluation of Text and Discourse with Coh-Metrix*. Cambridge
  University Press.
- Graesser, A. C., McNamara, D. S., & Kulikowich, J. M. (2011). Coh-Metrix:
  Providing multilevel analyses of text characteristics. *Educational
  Researcher*, 40(5), 223-234.
- McCarthy, P. M., & Jarvis, S. (2010). MTLD, vocd-D, and HD-D: A validation
  study of sophisticated approaches to lexical diversity assessment. *Behavior
  Research Methods*, 42(2), 381-392.
- Covington, M. A., & McFall, J. D. (2010). Cutting the Gordian knot: The
  moving-average type-token ratio (MATTR). *Journal of Quantitative
  Linguistics*, 17(2), 94-100.
- Flesch, R. (1948). A new readability yardstick. *Journal of Applied
  Psychology*, 32(3), 221-233.
- Kincaid, J. P., Fishburne, R. P., Rogers, R. L., & Chissom, B. S. (1975).
  *Derivation of new readability formulas (Automated Readability Index, Fog
  Count and Flesch Reading Ease Formula) for Navy enlisted personnel*. Research
  Branch Report 8-75, Naval Technical Training Command.

Lemmatizer tables and stop words come from spaCy (MIT); synonyms and lemma data
derive from Princeton WordNet 3.0. The parser weights (CC BY-SA 4.0) were
learned from UD English EWT and Wikipedia text; the news-and-magazine frequency
tables (CC BY 4.0) were counted from scratch from Common Pile, Wikinews,
Foodista and Project Gutenberg text, not derived from COCA or from any other
tool's frequency lists; the word vectors come from GloVe (PDDL), WikiText-103
(CC BY-SA 3.0) and vectors distilled from all-MiniLM-L6-v2 (Apache 2.0); word
frequencies (CC BY 4.0) were counted from Common Pile and Wikinews text;
syllable counts come from CMUdict (BSD) and the hyph_en_US patterns
(BSD-style). Each data file's licence and attribution are in [NOTICE](NOTICE).

## License

MIT. See [LICENSE](LICENSE); third-party data licences are in
[NOTICE](NOTICE).

## Every property

<!-- properties:start -->

Generated by `tools/property_table.py`; don't edit it by hand.

- **Python** means the value is computed locally, with no Jev request.
- **Jev: …** names the proseweave function whose Jev answers the value depends on.
- **(no key needed)** means the value is still produced without a Jev key, using
  the local fallback.

Jev is used by:

- `analysis.easability`: reader-level judgements behind narrativity, concreteness and the cohesion components
- `annotate.demonstrative_roles`: whether this/that/these/those is a determiner, a pronoun, a relative or a complementiser
- `annotate.familiarity`: how familiar a word is, as a stand-in for its frequency
- `annotate.phrase_familiarity`: how common a word or phrase is in ordinary writing
- `annotate.relatedness`: how related two passages are, on a graded scale
- `connectives.clause_marks`: whether a word like 'before', 'since' or 'as' introduces a clause or a noun phrase, in context
- `connectives.senses_jev`: the sense of an ambiguous connective in context ('so', 'since', 'while', ...)
- `tagger_classes.pos_tags`: word classes. The local tagger (syntax.py) tags every word; Jev re-checks only the open-class words the tagger is unsure of

| property | group | runs on | method |
|---|---|---|---|
| `addition` | connective | Jev: `connectives.senses_jev`, `tagger_classes.pos_tags` (no key needed) | `connectives.indices` |
| `all_additive` | connective | Jev: `connectives.senses_jev`, `tagger_classes.pos_tags` (no key needed) | `connectives.indices` |
| `all_causal` | connective | Jev: `connectives.senses_jev` (no key needed) | `connectives.indices` |
| `all_connective` | connective | Jev: `connectives.senses_jev`, `tagger_classes.pos_tags` (no key needed) | `connectives.indices` |
| `all_demonstratives` | connective | Python (no key needed) | `cohesion.closed_connectives` |
| `all_logical` | connective | Jev: `connectives.senses_jev`, `tagger_classes.pos_tags` (no key needed) | `connectives.indices` |
| `all_negative` | connective | Jev: `connectives.senses_jev` (no key needed) | `connectives.indices` |
| `all_positive` | connective | Jev: `connectives.senses_jev`, `tagger_classes.pos_tags` (no key needed) | `connectives.indices` |
| `all_temporal` | connective | Jev: `connectives.senses_jev` (no key needed) | `connectives.indices` |
| `attended_demonstratives` | connective | Jev: `annotate.demonstrative_roles` (no key needed) | `cohesion.closed_connectives` |
| `basic_connectives` | connective | Python (no key needed) | `cohesion.closed_connectives` |
| `conjunctions` | connective | Python (no key needed) | `cohesion.closed_connectives` |
| `coordinating_conjuncts` | connective | Jev: `annotate.demonstrative_roles`, `connectives.clause_marks`, `connectives.senses_jev` (no key needed) | `analysis.Analysis.cohesion` |
| `determiners` | connective | Python (no key needed) | `cohesion.closed_connectives` |
| `disjunctions` | connective | Python (no key needed) | `cohesion.closed_connectives` |
| `lexical_subordinators` | connective | Jev: `connectives.clause_marks`, `tagger_classes.pos_tags` (no key needed) | `cohesion.closed_connectives` |
| `negative_logical` | connective | Jev: `connectives.senses_jev` (no key needed) | `connectives.indices` |
| `opposition` | connective | Jev: `connectives.senses_jev` (no key needed) | `connectives.indices` |
| `order` | connective | Jev: `connectives.senses_jev` (no key needed) | `connectives.indices` |
| `positive_causal` | connective | Jev: `connectives.senses_jev` (no key needed) | `connectives.indices` |
| `positive_intentional` | connective | Jev: `connectives.senses_jev` (no key needed) | `connectives.indices` |
| `positive_logical` | connective | Jev: `connectives.senses_jev`, `tagger_classes.pos_tags` (no key needed) | `connectives.indices` |
| `reason_and_purpose` | connective | Jev: `connectives.senses_jev` (no key needed) | `connectives.indices` |
| `sentence_linking` | connective | Jev: `connectives.senses_jev` (no key needed) | `connectives.indices` |
| `unattended_demonstratives` | connective | Jev: `annotate.demonstrative_roles` (no key needed) | `cohesion.closed_connectives` |
| `deep_cohesion_construct` | construct | Jev: `connectives.senses_jev`, `tagger_classes.pos_tags` (no key needed) | `judged.compose` |
| `referential_cohesion_construct` | construct | Jev: `tagger_classes.pos_tags` (no key needed) | `judged.compose` |
| `n_paragraphs` | count | Python (no key needed) | `analysis.Analysis._basic_local_uncached` |
| `n_sentences` | count | Python (no key needed) | `analysis.Analysis._basic_local_uncached` |
| `n_tokens` | count | Python (no key needed) | `analysis.Analysis._basic_local_uncached` |
| `n_types` | count | Python (no key needed) | `analysis.Analysis._basic_local_uncached` |
| `text_length` | count | Python (no key needed) | `analysis.Analysis._basic_local_uncached` |
| `word_count` | count | Python (no key needed) | `analysis.Analysis._basic_local_uncached` |
| `lexical_density_tokens` | density | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `lexical_density_types` | density | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `deep_cohesion` | easability | Jev: `analysis.easability`, `annotate.demonstrative_roles`, `annotate.relatedness`, `connectives.senses_jev`, `tagger_classes.pos_tags` | `judged.compose` |
| `narrativity` | easability | Jev: `analysis.easability`, `annotate.demonstrative_roles`, `annotate.relatedness`, `connectives.senses_jev`, `tagger_classes.pos_tags` | `analysis.Analysis.easability` |
| `referential_cohesion` | easability | Jev: `analysis.easability`, `annotate.demonstrative_roles`, `annotate.relatedness`, `connectives.senses_jev`, `tagger_classes.pos_tags` | `judged.compose` |
| `syntactic_simplicity` | easability | Jev: `analysis.easability`, `annotate.demonstrative_roles`, `annotate.relatedness`, `connectives.senses_jev`, `tagger_classes.pos_tags` (no key needed) | `judged.compose` |
| `word_concreteness` | easability | Jev: `analysis.easability`, `annotate.demonstrative_roles`, `annotate.relatedness`, `connectives.senses_jev`, `tagger_classes.pos_tags` | `analysis.Analysis.easability` |
| `zipf_mean` | frequency | Jev: `annotate.familiarity` (no key needed) | `zipf.zipf_features` |
| `zipf_std` | frequency | Jev: `annotate.familiarity` (no key needed) | `zipf.zipf_features` |
| `pronoun_density` | givenness | Jev: `annotate.demonstrative_roles` (no key needed) | `cohesion.givenness` |
| `pronoun_noun_ratio` | givenness | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.givenness` |
| `repeated_content_and_pronoun_lemmas` | givenness | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.givenness` |
| `repeated_content_lemmas` | givenness | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.givenness` |
| `sent_len_cv` | length | Python (no key needed) | `analysis.Analysis._basic_local_uncached` |
| `sent_len_mean` | length | Python (no key needed) | `analysis.Analysis._basic_local_uncached` |
| `sent_len_std` | length | Python (no key needed) | `analysis.Analysis._basic_local_uncached` |
| `mtld_score` | lexical | Python (no key needed) | `analysis.Analysis._basic_local_uncached` |
| `type_token_ratio` | lexical | Python (no key needed) | `analysis.Analysis._basic_local_uncached` |
| `adjacent_overlap_2_adj_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_adj_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_adj_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_adj_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_adv_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_adv_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_adv_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_adv_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_all_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_all_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_all_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_all_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_argument_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_argument_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_argument_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_argument_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_cw_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_cw_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_cw_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_cw_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_fw_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_fw_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_fw_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_fw_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_noun_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_noun_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_noun_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_noun_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_pronoun_para` | overlap | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_pronoun_para_div_seg` | overlap | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_pronoun_sent` | overlap | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_pronoun_sent_div_seg` | overlap | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_verb_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_verb_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_verb_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_2_verb_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_adj_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_adj_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_adj_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_adj_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_adv_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_adv_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_adv_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_adv_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_all_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_all_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_all_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_all_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_argument_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_argument_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_argument_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_argument_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_adj_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_adj_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_adv_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_adv_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_all_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_all_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_argument_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_argument_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_cw_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_cw_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_fw_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_fw_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_noun_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_noun_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_pronoun_para` | overlap | Jev: `annotate.demonstrative_roles` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_pronoun_sent` | overlap | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_verb_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_2_verb_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_adj_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_adj_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_adv_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_adv_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_all_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_all_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_argument_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_argument_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_cw_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_cw_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_fw_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_fw_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_noun_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_noun_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_pronoun_para` | overlap | Jev: `annotate.demonstrative_roles` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_pronoun_sent` | overlap | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_verb_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_binary_verb_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_cw_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_cw_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_cw_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_cw_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_fw_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_fw_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_fw_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_fw_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_noun_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_noun_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_noun_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_noun_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_pronoun_para` | overlap | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_pronoun_para_div_seg` | overlap | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_pronoun_sent` | overlap | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_pronoun_sent_div_seg` | overlap | Jev: `annotate.demonstrative_roles`, `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_verb_para` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_verb_para_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_verb_sent` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adjacent_overlap_verb_sent_div_seg` | overlap | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.overlap_family` |
| `adj_ratio` | pos | Jev: `tagger_classes.pos_tags` (no key needed) | `analysis.Analysis.word_classes` |
| `adv_ratio` | pos | Jev: `tagger_classes.pos_tags` (no key needed) | `analysis.Analysis.word_classes` |
| `noun_ratio` | pos | Jev: `tagger_classes.pos_tags` (no key needed) | `analysis.Analysis.word_classes` |
| `verb_ratio` | pos | Jev: `tagger_classes.pos_tags` (no key needed) | `analysis.Analysis.word_classes` |
| `overall_quality` | quality | Jev: `analysis.easability`, `annotate.demonstrative_roles`, `annotate.relatedness`, `connectives.senses_jev`, `tagger_classes.pos_tags` | `judged.compose` |
| `automated_readability_index` | readability | Python (no key needed) | `readability.scores` |
| `flesch_kincaid_grade` | readability | Python (no key needed) | `readability.scores` |
| `flesch_reading_ease` | readability | Python (no key needed) | `readability.scores` |
| `lda_1_all_para` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `lda_1_all_sent` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `lda_2_all_para` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `lda_2_all_sent` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `lsa_1_all_para` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `lsa_1_all_sent` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `lsa_2_all_para` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `lsa_2_all_sent` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `paragraph_cohesion_mean` | semantic | Jev: `annotate.relatedness` (no key needed) | `similarity.sentence_cohesion` |
| `paragraph_cohesion_std` | semantic | Jev: `annotate.relatedness` (no key needed) | `similarity.sentence_cohesion` |
| `semantic_cohesion_max` | semantic | Jev: `annotate.relatedness` (no key needed) | `similarity.sentence_cohesion` |
| `semantic_cohesion_mean` | semantic | Jev: `annotate.relatedness` (no key needed) | `similarity.sentence_cohesion` |
| `semantic_cohesion_min` | semantic | Jev: `annotate.relatedness` (no key needed) | `similarity.sentence_cohesion` |
| `semantic_cohesion_std` | semantic | Jev: `annotate.relatedness` (no key needed) | `similarity.sentence_cohesion` |
| `word2vec_1_all_para` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `word2vec_1_all_sent` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `word2vec_2_all_para` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `word2vec_2_all_sent` | semantic | Jev: `tagger_classes.pos_tags` (no key needed) | `similarity.segment_indices` |
| `syn_overlap_para_noun` | synonym | Jev: `tagger_classes.pos_tags` (no key needed) | `analysis.Analysis.cohesion` |
| `syn_overlap_para_verb` | synonym | Jev: `tagger_classes.pos_tags` (no key needed) | `analysis.Analysis.cohesion` |
| `syn_overlap_sent_noun` | synonym | Jev: `tagger_classes.pos_tags` (no key needed) | `analysis.Analysis.cohesion` |
| `syn_overlap_sent_verb` | synonym | Jev: `tagger_classes.pos_tags` (no key needed) | `analysis.Analysis.cohesion` |
| `dep_distance_mean` | syntax | Python (no key needed) | `analysis.Analysis.dependency` |
| `dep_distance_std` | syntax | Python (no key needed) | `analysis.Analysis.dependency` |
| `adj_ttr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `adv_ttr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `argument_ttr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `bigram_lemma_ttr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `content_ttr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `function_mattr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `function_ttr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `lemma_mattr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `lemma_ttr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `noun_ttr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `prp_ttr` | ttr | Jev: `annotate.demonstrative_roles` (no key needed) | `cohesion.ttr_family` |
| `trigram_lemma_ttr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `verb_ttr` | ttr | Jev: `tagger_classes.pos_tags` (no key needed) | `cohesion.ttr_family` |
| `mag_news_a_n_bi_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_a_n_quad_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_a_n_tri_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_adj_bi_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_adj_quad_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_adj_tri_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_adj_uni_keywords_percentage` | source comparison | Jev: `annotate.phrase_familiarity`, `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_bi_keywords_percentage` | source comparison | Jev: `annotate.demonstrative_roles`, `annotate.phrase_familiarity`, `connectives.clause_marks`, `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_n_bi_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_n_quad_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_n_tri_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_n_uni_keywords_percentage` | source comparison | Jev: `annotate.phrase_familiarity`, `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_quad_keywords_percentage` | source comparison | Jev: `annotate.demonstrative_roles`, `annotate.phrase_familiarity`, `connectives.clause_marks`, `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_tri_keywords_percentage` | source comparison | Jev: `annotate.demonstrative_roles`, `annotate.phrase_familiarity`, `connectives.clause_marks`, `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_uni_keywords_percentage` | source comparison | Jev: `annotate.phrase_familiarity`, `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_v_bi_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_v_n_bi_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_v_n_quad_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_v_n_tri_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_v_n_uni_keywords_percentage` | source comparison | Jev: `annotate.phrase_familiarity`, `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_v_quad_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_v_tri_keywords_percentage` | source comparison | Jev: `tagger_classes.pos_tags` | `source.compare` |
| `mag_news_v_uni_keywords_percentage` | source comparison | Jev: `annotate.phrase_familiarity`, `tagger_classes.pos_tags` | `source.compare` |
| `source_similarity_lda` | source comparison | Jev: `tagger_classes.pos_tags` | `similarity.source_indices` |
| `source_similarity_lsa` | source comparison | Jev: `tagger_classes.pos_tags` | `similarity.source_indices` |
| `source_similarity_word2vec` | source comparison | Jev: `tagger_classes.pos_tags` | `similarity.source_indices` |

204 single-text and 26 source-comparison properties: 21 computed in Python alone, 209 using Jev.

<!-- properties:end -->

## Every cadence measurement

`cadence.measure()` is separate from `properties()` and needs no key. Columns
are equal-length lists, one entry per sentence, paragraph or pattern. Rhythm
statistics marked † are `{value, null_mean, z}`: the value, its mean over 20
seeded shuffles of the same text at the level it reads, and a z against them.

| block | fields |
|---|---|
| `summary` | `sentences`, `prose_sentences`, `paragraphs`, `type_counts`, `words`, `prose_words`, `prose_syllables`, `one_line_paragraphs`, `prose_length_percentiles` (p10, p25, median, p75, p90), `local_cv` (p20, median) |
| `sentences` | `index`, `paragraph`, `type_code`, `start`, `end`, `words`, `syllables`, `stresses`, `final_stress_offset`, `phrase_start`, `phrases`, `pause_count`, `pause_positions`, `relations`, `overlap_ratio`, `opening_sim_prev`, `skeleton_sim_prev`, `opens_with_reference`, `is_paragraph_final`, `is_standalone` |
| `paragraphs` | `index`, `type_code`, `start`, `end`, `words`, `sentences`, `first_sentence`, `final_ratio`, `initial_ratio` |
| `phrases` | `syllables` (every phrase's length, flat; a sentence's run starts at its `phrase_start`) |
| `patterns` | spans (`start`, `end`, plus the numbers named) for `flat_stretches` (`run_cv`), `long_runs`, `short_runs`, `repeated_structure` (`by`, `skeleton_sim`), `repeated_terminology` (`term_start`, `term_end`, `skeleton_sim`), `disconnected_runs`, `dense_relations` (`sentence`, `relations`), `emphasis_points` (`sentence`, `neighbour_median`, `shorter_than_neighbours`), `short_paragraphs`, `even_paragraph_runs` (`run_cv`); `counts` of each; `flat_stretch_share`; the document `thresholds` they were found against |
| `rhythm.beat` | `syllables`, `stresses`, `clash_rate`†, `alternation_share`†, `lapse_rate`†, `ending_stressed`† |
| `rhythm.phrase` | `phrases`, `phrase_contrast`†, `end_weight`†, `endings` (share of sentences ending 0, 1, 2+ syllables after the last stress) |
| `rhythm.landing` | `paragraphs`, `final_ratio`†, `initial_ratio`† |
| `rhythm.contour` | `window`, `sentence`, `smooth`, `local_variation`, `alternation`† |

`cadence.align(before, after)` returns `passages` as columns of paragraph spans
in each version, a status code (0 unchanged, 1 edited, 2 split, 3 merged,
4 converted to another content type, 5 inserted, 6 deleted), a similarity and
part counts.
