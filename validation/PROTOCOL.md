# Validation protocol

Written before any agreement number was looked at, so the pass mark cannot be
moved to fit the results.

## What is measured

228 properties: 28 basic linguistic features (counts, lexical diversity,
sentence length, readability, word classes, word familiarity, semantic
cohesion, dependency distance), 168 single-text cohesion indices, the five
easability components and an overall quality score, and 26 properties that
exist only when a text is compared with a source text. That is 202
single-text properties and 26 source properties.

## The reference

Reference outputs: TAACO 2.0 for the cohesion and source indices, a
spaCy-based feature script for the basic features, and an LLM judge for the
easability components described by Graesser, McNamara & Kulikowich (2011)
(run by us in a pinned environment; not redistributed). For MTLD,
proseweave follows the published algorithm (McCarthy & Jarvis 2010), and the
reference values were checked against that algorithm.

## The rule for choosing an implementation

Routes are tried in this order for each property:

1. **Jev-direct** - Jev is asked for the property as a Score question on the
   whole text.
2. **Jev-annotated** - Jev supplies the linguistic judgements that usually come
   from trained models (word class in context, how related two segments are,
   synonymy, word familiarity), and a formula in standard-library Python
   computes the index from them.
3. **Standard library only** - rules and arithmetic, no Jev.

The first route that passes is the one shipped. A property falls back from Jev
only when both Jev routes fail. That failure is the proof, and it is recorded.
A property is dropped only if no route can be built at all, with the reason.

## The pass mark

Across the 108-text validation corpus, **Spearman rank correlation with the
reference of at least 0.80**, and the lower bound of a bootstrap 90% interval
of at least 0.70, so a lucky sample cannot carry a weak route over the line.

Rank correlation is the primary test because these numbers are used to compare
texts - a draft against its author, a rewrite against its original.

Properties whose reference values barely vary across the corpus cannot be
tested by rank. They are reported separately.

## Constraints on the code

Standard library only. Jev is called over `urllib`. No spaCy, torch,
scikit-learn, NLTK, wordfreq or gensim at run time, and no data file under a
restrictive licence. No code, word lists or data files from TAACO or Coh-Metrix
are used. Each index follows its published definition, and agreement with those
tools' outputs is what this protocol measures.

## The corpus

108 texts, up to ~1,000 words each: four from each of 26 categories in
literary and commercial registers (literary essay, longform journalism,
science, memoir, obituary, technical writing ... and listicle, SEO article,
press release, corporate blog, social post), plus four chapters of a novel. The
texts are copyrighted and are not redistributed (see README.md here).

## Amendment (September 2026): a second corpus

The original text above is unchanged in substance; later edits only renamed
the categories and named the reference tools. After the first round, a second, open
corpus was added (`open/`): 108 texts under public-domain, CC0, CC BY and
CC BY-SA terms, which anyone can rebuild. The pass mark is the same. A
property now counts as validated only if it passes on **both** corpora. The
108-text corpus described above is the article corpus (`articles/`).

Anything tuned (wordings, weights, feature choices) is chosen on the
even-numbered texts and reported on the odd-numbered ones.

The six judge-scale properties (narrativity, word_concreteness,
syntactic_simplicity, referential_cohesion, deep_cohesion, overall_quality)
have an LLM judge as their reference. A single run of that judge repeats at
rho 0.77-0.98 depending on the property (0.77-0.83 for the three cohesion and
quality scores), so these properties are validated against the mean of 10
judge runs on the article corpus and 6 on the open corpus, whose reliability
is 0.94-1.00. `judge_retest.json` (in this folder) gives the per-property figures for both
corpora: agreement between single runs, split-half agreement and the
reliability of the mean.


### Note (26 September 2026): adopting changes that move source-comparison properties

With 60 source/target pairs per corpus, single source-comparison indices near
the bar move across it between fresh runs of the same code, because Jev's
answers vary slightly from run to run. A change that affects these properties
is therefore adopted when all three hold:

1. no single-text property loses its pass (strict, on one fresh run);
2. the combined source-property pass count over both corpora, averaged over at
   least two fresh runs, is within 0.5 of the same average for the current
   version;
3. the mean rho of the keyness indices does not fall.

The pass mark itself is unchanged.
