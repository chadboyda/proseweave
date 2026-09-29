# Results: source-comparison properties

60 (source, target) pairs drawn from each corpus, compared with the reference outputs from
TAACO 2.0. Same pass mark as RESULTS.md: Spearman rho >= 0.80 and a bootstrap 90% lower
bound >= 0.70. The reference outputs are not redistributed; to reproduce, generate your
own reference values by running the reference tools on the corpus texts and run
`python3 score.py my_reference_source_pairs.json articles/proseweave_source_pairs.json`
(and the same for `open/`). See README.md here.

**15 of 26 pass on both corpora** (article corpus 17, open corpus 20).

With 60 pairs, single pair properties vary noticeably from run to run: repeated fresh runs
moved individual indices by up to 0.1 in rho and a pass count by 1-2, because Jev's answers
differ slightly between runs. Read the pass counts and mean rho across the family rather
than any one index. The numbers here come from a cached, reproducible run. Indices seen
to move across the bar between runs of identical or near-identical code:
`mag_news_n_uni`, `mag_news_v_uni`, `mag_news_v_n_uni`, `mag_news_v_bi` and `mag_news_a_n_quad`.
For that reason a change is adopted on pair counts averaged over at least two fresh runs
(PROTOCOL.md).

The current version (the keyword lists on the main parse, with the table counted by
proseweave's own pipeline) was adopted on five fresh runs whose combined pass counts over
both corpora were 39, 37, 37, 37 and 37 (mean 37.4), against 38, 37 and 38 (mean 37.67)
for the version before it, with the keyness mean rho up from 0.874 to 0.886. In the
published run, `mag_news_v_bi` (article corpus) and `mag_news_v_uni` (open corpus) sit at
the bar, missing on the lower bound.

| property | article corpus rho / lower90 | open corpus rho / lower90 |
|---|---|---|
| `mag_news_a_n_bi_keywords_percentage` | 0.78 / 0.66 (below) | 0.94 / 0.88 |
| `mag_news_a_n_quad_keywords_percentage` | 0.98 / 0.95 | 0.90 / 0.82 |
| `mag_news_a_n_tri_keywords_percentage` | 0.89 / 0.80 | 0.95 / 0.89 |
| `mag_news_adj_bi_keywords_percentage` | 0.73 / 0.58 (below) | 0.93 / 0.87 |
| `mag_news_adj_quad_keywords_percentage` | 0.90 / 0.84 | 0.92 / 0.85 |
| `mag_news_adj_tri_keywords_percentage` | 0.86 / 0.77 | 0.90 / 0.81 |
| `mag_news_adj_uni_keywords_percentage` | 0.66 / 0.49 (below) | 0.72 / 0.55 (below) |
| `mag_news_bi_keywords_percentage` | 1.00 / 0.99 | 0.99 / 0.98 |
| `mag_news_n_bi_keywords_percentage` | 0.77 / 0.64 (below) | 0.93 / 0.84 |
| `mag_news_n_quad_keywords_percentage` | 0.87 / 0.79 | 0.92 / 0.85 |
| `mag_news_n_tri_keywords_percentage` | 0.74 / 0.59 (below) | 0.94 / 0.86 |
| `mag_news_n_uni_keywords_percentage` | 0.96 / 0.89 | 0.74 / 0.56 (below) |
| `mag_news_quad_keywords_percentage` | flat reference | flat reference |
| `mag_news_tri_keywords_percentage` | 1.00 / 1.00 | 1.00 / 1.00 |
| `mag_news_uni_keywords_percentage` | 0.90 / 0.83 | 0.89 / 0.78 |
| `mag_news_v_bi_keywords_percentage` | 0.81 / 0.70 (below) | 0.89 / 0.81 |
| `mag_news_v_n_bi_keywords_percentage` | 0.88 / 0.81 | 0.90 / 0.81 |
| `mag_news_v_n_quad_keywords_percentage` | 0.98 / 0.94 | 0.99 / 0.96 |
| `mag_news_v_n_tri_keywords_percentage` | 0.99 / 0.98 | 0.98 / 0.95 |
| `mag_news_v_n_uni_keywords_percentage` | 0.83 / 0.75 | 0.77 / 0.61 (below) |
| `mag_news_v_quad_keywords_percentage` | 0.94 / 0.89 | 0.90 / 0.83 |
| `mag_news_v_tri_keywords_percentage` | 0.93 / 0.88 | 0.94 / 0.89 |
| `mag_news_v_uni_keywords_percentage` | 0.70 / 0.55 (below) | 0.81 / 0.69 (below) |
| `source_similarity_lda` | 0.78 / 0.67 (below) | 0.78 / 0.66 (below) |
| `source_similarity_lsa` | 0.89 / 0.83 | 0.88 / 0.80 |
| `source_similarity_word2vec` | 0.90 / 0.82 | 0.89 / 0.81 |
