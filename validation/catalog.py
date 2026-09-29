"""Every single-text property, described in plain words for Jev.

Used by the Jev-direct route: each property becomes one Score question whose
levels describe situations rather than degrees, which is what Jev's docs ask
for - a level is evaluated on its own and never sees its neighbours, so
"moderate" means nothing and "about half the sentences pick up a noun from the
one before" does.

Each entry is property -> (group, family, question, levels). The property names
are the ones proseweave emits.
"""

WORD_CLASS = {
    "all":      ("words", "any word at all"),
    "cw":       ("content words", "the meaning-carrying words: nouns, main verbs, adjectives and adverbs"),
    "fw":       ("function words", "the small grammatical words such as the, of, and, to, it, was"),
    "noun":     ("nouns", "nouns"),
    "verb":     ("verbs", "verbs"),
    "adj":      ("adjectives", "adjectives"),
    "adv":      ("adverbs", "adverbs"),
    "pronoun":  ("pronouns", "pronouns such as he, she, it, they, we"),
    "argument": ("nouns and pronouns", "nouns and pronouns - the words that name who or what a sentence is about"),
}
UNIT = {"sent": ("sentence", "sentences"), "para": ("paragraph", "paragraphs")}


def levels4(low, low_short, high_short, high):
    return [low,
            f"Mostly {low_short}, with the occasional exception",
            f"Mostly {high_short}, with the occasional exception",
            high]


def overlap_props():
    out = {}
    for cls, (name, gloss) in WORD_CLASS.items():
        for unit, (u, us) in UNIT.items():
            for win in ("", "2_"):
                reach = f"the {u} right after it" if not win else f"the next two {us}"
                base = f"{win}{cls}_{unit}"
                q = (f"Consider how each {u} relates to {reach}. How much do they repeat the same "
                     f"{name} ({gloss})? Count a word as repeated if the same word or another form of "
                     f"it (walk / walked) appears in both.")
                lv = levels4(f"{us.capitalize()} almost never repeat {name} from {reach}; each brings in new ones",
                             f"{us} that bring in new {name}",
                             f"{us} that reuse {name} from {reach}",
                             f"Nearly every {u} reuses several {name} from {reach}")
                out[f"adjacent_overlap_{base}"] = ("cohesion", "overlap", q, lv)
                out[f"adjacent_overlap_{base}_div_seg"] = ("cohesion", "overlap", q, lv)
                qb = (f"How often does a {u} share at least one of the same {name} ({gloss}) with "
                      f"{reach}?")
                lvb = levels4(f"Almost no {u} shares any {name} with {reach}",
                              f"{us} that share none of their {name} with {reach}",
                              f"{us} that share at least one of their {name} with {reach}",
                              f"Virtually every {u} shares at least one of its {name} with {reach}")
                out[f"adjacent_overlap_binary_{base}"] = ("cohesion", "overlap", qb, lvb)
    return out


def semantic_props():
    out = {}
    for model, label in (("lsa", "LSA"), ("lda", "LDA"), ("word2vec", "word2vec")):
        for win in ("1", "2"):
            for unit, (u, us) in UNIT.items():
                reach = f"the {u} right after it" if win == "1" else f"the next two {us}"
                q = (f"How close in meaning is each {u} to {reach} - are they about the same thing, "
                     f"even where they use different words?")
                lv = levels4(f"Each {u} is about something quite different from {reach}",
                             f"{us} that move to a new subject", f"{us} that stay on the same subject",
                             f"Each {u} is about almost exactly the same thing as {reach}")
                out[f"{model}_{win}_all_{unit}"] = ("cohesion", "semantic", q, lv)
    for unit, (u, us) in UNIT.items():
        for pos, pname in (("noun", "nouns"), ("verb", "verbs")):
            q = (f"How often does a {u} use a synonym of one of the {pname} in the {u} before it - a "
                 f"different word with the same meaning, rather than the same word again?")
            lv = levels4(f"{us.capitalize()} almost never echo the previous {u}'s {pname} with synonyms",
                         f"{us} with no synonyms of the previous {u}'s {pname}",
                         f"{us} that echo the previous {u}'s {pname} with a synonym",
                         f"Nearly every {u} restates several of the previous {u}'s {pname} with synonyms")
            out[f"syn_overlap_{unit}_{pos}"] = ("cohesion", "synonym", q, lv)
    return out


TTR = {
    "lemma_ttr": "of all its words, counting walk and walked as one",
    "lemma_mattr": "of all its words, measured over short moving windows",
    "content_ttr": "of its content words - nouns, main verbs, adjectives, adverbs",
    "function_ttr": "of its small grammatical words",
    "function_mattr": "of its small grammatical words, measured over short moving windows",
    "noun_ttr": "of its nouns", "verb_ttr": "of its verbs", "adj_ttr": "of its adjectives",
    "adv_ttr": "of its adverbs", "prp_ttr": "of its pronouns", "argument_ttr": "of its nouns and pronouns",
    "bigram_lemma_ttr": "of its two-word sequences", "trigram_lemma_ttr": "of its three-word sequences",
}


def ttr_props():
    out = {}
    for k, what in TTR.items():
        q = (f"How varied is the text's vocabulary {what}? Does it keep reusing the same ones, or "
             f"does almost every one appear only once?")
        lv = levels4("The same few keep coming back again and again",
                     "repetition of the same ones", "fresh ones each time",
                     "Almost every one is different; hardly any is repeated")
        out[k] = ("cohesion", "ttr", q, lv)
    out["lexical_density_tokens"] = ("cohesion", "density",
        "What share of the running words are content words (nouns, main verbs, adjectives, adverbs) "
        "rather than small grammatical words?",
        levels4("Mostly small grammatical words; content words are sparse",
                "grammatical words", "content words",
                "Packed with content words; grammatical words are minimal"))
    out["lexical_density_types"] = ("cohesion", "density",
        "Among the distinct words the text uses, what share are content words rather than grammatical words?",
        out["lexical_density_tokens"][3])
    return out


CONNECTIVES = {
    "basic_connectives": "basic connecting words such as and, but, so, because, then",
    "conjunctions": "conjunctions joining clauses, such as and, but, or, yet",
    "disjunctions": "words presenting alternatives, such as or, either, otherwise",
    "lexical_subordinators": "subordinating words such as although, because, while, unless, whereas",
    "coordinating_conjuncts": "linking adverbs such as however, therefore, moreover, meanwhile",
    "addition": "words that add a point, such as also, moreover, in addition, furthermore",
    "sentence_linking": "sentence-opening links such as however, nevertheless, so, then",
    "order": "sequencing words such as first, next, then, finally, to begin",
    "reason_and_purpose": "words giving a reason or purpose, such as because, so that, in order to",
    "all_causal": "words expressing cause and effect, positive or negative",
    "positive_causal": "words linking a cause to its effect, such as because, so, therefore, as a result",
    "opposition": "words setting things against each other, such as but, however, although, whereas",
    "determiners": "determiners such as the, a, this, those, every",
    "all_demonstratives": "demonstratives: this, that, these, those",
    "attended_demonstratives": "demonstratives followed by a noun, as in 'this idea'",
    "unattended_demonstratives": "demonstratives standing alone, as in 'this is wrong'",
    "all_additive": "words that add or extend, such as and, also, as well",
    "all_logical": "logical connectives of any kind: and, or, but, if, so",
    "positive_logical": "connectives that extend an argument: and, also, so, then",
    "negative_logical": "connectives that qualify or reverse: but, however, although, yet",
    "all_temporal": "words placing events in time, such as when, then, after, before, meanwhile",
    "positive_intentional": "words expressing purpose or intention, such as in order to, so that, to",
    "all_positive": "connectives that extend or build on what came before",
    "all_negative": "connectives that contrast with or deny what came before",
    "all_connective": "connecting words and phrases of every kind",
}


def connective_props():
    out = {}
    for k, what in CONNECTIVES.items():
        q = f"How densely does the text use {what}?"
        lv = levels4(f"Hardly any {what.split(',')[0]} anywhere",
                     "sentences without them", "sentences that use them",
                     f"They appear constantly, several in most sentences")
        out[k] = ("cohesion", "connective", q, lv)
    return out


def givenness_props():
    return {
        "pronoun_density": ("cohesion", "givenness",
            "How much does the text refer back to things with pronouns (he, it, they) and stand-alone "
            "this/that, instead of naming them again?",
            levels4("Things are named outright; pronouns are rare",
                    "naming things outright", "referring back with pronouns",
                    "Pronouns and stand-alone this/that everywhere")),
        "pronoun_noun_ratio": ("cohesion", "givenness",
            "Compared with how many nouns it uses, how many pronouns does the text use?",
            levels4("Far more nouns than pronouns", "nouns", "pronouns",
                    "About as many pronouns as nouns, or more")),
        "repeated_content_lemmas": ("cohesion", "givenness",
            "How much of the text's content vocabulary is repeated - words that come back after they "
            "are first used, rather than appearing once?",
            levels4("Almost every content word appears once and is never picked up again",
                    "words used once", "words that come back",
                    "The same content words keep returning throughout")),
        "repeated_content_and_pronoun_lemmas": ("cohesion", "givenness",
            "Counting both content words and pronouns, how much does the text return to what it has "
            "already mentioned?",
            levels4("Almost nothing already mentioned is picked up again",
                    "new material", "returning to earlier material",
                    "It keeps circling back to what it has already mentioned")),
    }


def basic_props():
    L = levels4
    return {
        "n_tokens": ("basic", "count", "How long is the text?",
                     L("A few sentences", "a short piece", "a long piece", "Many pages")),
        "n_types": ("basic", "count", "How many different distinct words does the text use in total?",
                    L("Very few distinct words", "a small vocabulary", "a large vocabulary", "A great many distinct words")),
        "n_sentences": ("basic", "count", "How many sentences does the text have?",
                        L("Only a handful", "few sentences", "many sentences", "A great many sentences")),
        "n_paragraphs": ("basic", "count", "How many paragraphs does the text have?",
                         L("One or two", "few paragraphs", "many paragraphs", "Dozens of paragraphs")),
        "text_length": ("basic", "count", "How long is the text in characters?",
                        L("A few lines", "short", "long", "Very long")),
        "word_count": ("basic", "count", "How many words long is the text?",
                       L("A few dozen words", "short", "long", "Thousands of words")),
        "type_token_ratio": ("basic", "lexical", "How varied is the vocabulary - how often are words repeated?",
                             L("Constant repetition of the same words", "repetition", "variety", "Hardly a word repeated")),
        "mtld_score": ("basic", "lexical", "How wide is the vocabulary, sustained across the whole text?",
                       L("A narrow, repetitive vocabulary", "a narrow vocabulary", "a wide vocabulary",
                         "A very wide vocabulary that never settles into repetition")),
        "sent_len_mean": ("basic", "length", "How long are the sentences on average?",
                          L("Short, clipped sentences of a few words", "short sentences", "long sentences",
                            "Long sentences that run for several lines")),
        "sent_len_std": ("basic", "length", "How much does sentence length vary from one sentence to the next?",
                         L("Every sentence is about the same length", "similar lengths", "varied lengths",
                           "Very short and very long sentences mixed together")),
        "sent_len_cv": ("basic", "length", "Relative to their typical length, how uneven are the sentence lengths?",
                        L("Strikingly uniform sentence lengths", "uniform", "uneven",
                          "Wildly uneven sentence lengths")),
        "dep_distance_mean": ("basic", "syntax",
                              "How far apart are grammatically linked words, on average - does a sentence keep "
                              "related words close together, or separate them with long insertions?",
                              L("Related words sit right next to each other", "close links", "distant links",
                                "Long insertions constantly separate words that belong together")),
        "dep_distance_std": ("basic", "syntax",
                             "How much does that distance between linked words vary across the text?",
                             L("Uniformly compact syntax", "consistent", "variable",
                               "Some sentences very compact, others sprawling")),
        "zipf_mean": ("basic", "frequency", "How common and everyday are the words used?",
                      L("Rare, specialist or unusual words throughout", "uncommon words", "everyday words",
                        "Almost entirely very common everyday words")),
        "zipf_std": ("basic", "frequency", "How much does the text mix very common words with rare ones?",
                     L("All the words are of similar familiarity", "similar familiarity", "mixed familiarity",
                       "Everyday words and rare ones mixed throughout")),
        "flesch_reading_ease": ("basic", "readability", "How easy is the text to read?",
                                L("Hard going: long sentences and long words", "hard", "easy",
                                  "Very easy: short sentences, short common words")),
        "flesch_kincaid_grade": ("basic", "readability", "What school grade level does the text read at?",
                                 L("Early primary school", "primary school", "high school", "University level or above")),
        "automated_readability_index": ("basic", "readability",
                                        "How demanding is the text, judged by word and sentence length?",
                                        L("Very undemanding", "undemanding", "demanding", "Very demanding")),
        "noun_ratio": ("basic", "pos", "What share of the content words are nouns?",
                       L("Nouns are scarce", "few nouns", "many nouns", "Dominated by nouns")),
        "verb_ratio": ("basic", "pos", "What share of the content words are verbs?",
                       L("Verbs are scarce", "few verbs", "many verbs", "Dominated by verbs")),
        "adj_ratio": ("basic", "pos", "What share of the content words are adjectives?",
                      L("Adjectives are scarce", "few adjectives", "many adjectives", "Adjectives everywhere")),
        "adv_ratio": ("basic", "pos", "What share of the content words are adverbs?",
                      L("Adverbs are scarce", "few adverbs", "many adverbs", "Adverbs everywhere")),
        "semantic_cohesion_mean": ("basic", "semantic",
                                   "How closely does each sentence follow on in meaning from the one before?",
                                   L("Sentences jump between unrelated subjects", "jumps", "close follow-on",
                                     "Each sentence follows very closely from the last")),
        "semantic_cohesion_std": ("basic", "semantic",
                                  "How much does that closeness between neighbouring sentences vary?",
                                  L("Uniformly connected", "steady", "variable",
                                    "Some sentences follow closely, others leap away")),
        "semantic_cohesion_min": ("basic", "semantic",
                                  "What is the sharpest jump in meaning anywhere between two neighbouring sentences?",
                                  L("There is a complete change of subject somewhere", "a sharp jump",
                                    "only mild shifts", "Even the biggest shift is small")),
        "semantic_cohesion_max": ("basic", "semantic",
                                  "How close in meaning are the most closely linked pair of neighbouring sentences?",
                                  L("Even the closest pair differ a lot", "moderate at most", "close",
                                    "Some neighbouring sentences say nearly the same thing")),
        "paragraph_cohesion_mean": ("basic", "semantic",
                                    "How closely does each paragraph follow on in meaning from the one before?",
                                    L("Paragraphs jump between unrelated subjects", "jumps", "close follow-on",
                                      "Each paragraph follows very closely from the last")),
        "paragraph_cohesion_std": ("basic", "semantic",
                                   "How much does that closeness between neighbouring paragraphs vary?",
                                   L("Uniformly connected paragraphs", "steady", "variable",
                                     "Some paragraphs follow closely, others leap away")),
    }


def easability_props():
    """The five easability components plus an overall quality score.

    Level text follows Graesser, McNamara & Kulikowich (2011), which is where
    the components come from, so each level describes a situation a reader
    could recognise.
    """
    L = levels4
    return {
        "narrativity": ("easability", "easability",
            "How story-like is the text - people or agents doing things, events unfolding in time, everyday "
            "words - as opposed to expository or informational writing?",
            L("Purely informational or expository; no story at all", "informational writing",
              "storytelling", "A story throughout: characters, events, time moving forward")),
        "syntactic_simplicity": ("easability", "easability",
            "How simple is the sentence structure - few words before the main verb, short clauses, "
            "familiar patterns?",
            L("Complex, embedded sentences with long build-ups before the main verb",
              "complex syntax", "simple syntax", "Very simple, direct sentence structures throughout")),
        "word_concreteness": ("easability", "easability",
            "How concrete is the vocabulary - words for things you can see, touch and picture - as opposed "
            "to abstract ideas?",
            L("Almost entirely abstract ideas and concepts", "abstract words", "concrete words",
              "Almost entirely physical things you could see or touch")),
        "referential_cohesion": ("easability", "easability",
            "How much do the sentences keep referring to the same people, things and ideas, so the reader "
            "can track what is being talked about?",
            L("Each sentence introduces new referents; little is carried over",
              "new referents", "carried-over referents",
              "The same referents run clearly through the whole text")),
        "deep_cohesion": ("easability", "easability",
            "How explicitly does the text spell out causal and logical connections between ideas - "
            "because, so, therefore, in order to?",
            L("Ideas sit side by side with the connections left unstated",
              "unstated connections", "stated connections",
              "Causal and logical links are spelled out throughout")),
        "referential_cohesion_construct": ("easability", "construct",
            "How much does each sentence repeat nouns, arguments and content words from the one before?",
            L("Each sentence brings in new words; little is carried over", "new words",
              "repeated words", "Nearly every sentence reuses words from the one before")),
        "deep_cohesion_construct": ("easability", "construct",
            "How densely does the text use causal and logical connectives - because, so, therefore, if?",
            L("Almost no causal or logical connectives", "few connectives", "frequent connectives",
              "Causal and logical connectives in nearly every sentence")),
        "overall_quality": ("easability", "quality",
            "How well written is this text overall?",
            L("Poorly written: confused, clumsy or padded", "weak writing", "good writing",
              "Excellent writing: clear, precise and assured")),
    }


def all_props():
    out = {}
    for f in (basic_props, overlap_props, semantic_props, ttr_props, connective_props,
              givenness_props, easability_props):
        out.update(f())
    return out


if __name__ == "__main__":
    import collections
    p = all_props()
    print(len(p), "properties;", dict(collections.Counter(v[1] for v in p.values())))
