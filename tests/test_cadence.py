"""Cadence measurements (cadence.py): offline, on small synthetic texts."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
from proseweave import cadence

ROOT = Path(__file__).resolve().parent.parent

# Sentences of widely varying length, each opening differently.
VARIED = [
    "Rain came early that year.",
    "By the time the farmers had finished bringing in the last of the barley from the lower fields, the river "
    "had already risen past the old stone marker by the mill.",
    "Nobody was surprised.",
    "Grandmother said the swallows had warned us weeks before, flying low over the orchard and crowding under "
    "the eaves.",
    "She was often right.",
    "Down at the ford, water spilled across the road and carried branches, fence posts and a child's red bucket "
    "toward the bridge, where the debris gathered against the pillars in a tangled heap.",
    "Traffic stopped.",
    "For three days the village waited for the level to fall.",
    "Then it did.",
    "Mud covered everything that the flood had touched, from the lowest kitchen floors to the church steps, and "
    "the smell of it lingered well into the following month.",
    "Children loved it.",
    "Several families moved upstairs until their ground floors dried out.",
]
# Six sentences of 12-14 words with different openings and clause patterns.
FLAT = [
    "The committee reviewed the proposal carefully during its regular Tuesday morning meeting.",
    "Several members raised questions about the projected costs of the new building.",
    "After some discussion the chair asked the treasurer to prepare a revised budget.",
    "Everyone agreed that the revised figures would be circulated before the next session.",
    "In the meantime the architect was asked to simplify the design of the roof.",
    "Most of the members seemed satisfied with this cautious approach to the project.",
]
REPEAT_OPEN = [
    "We will rebuild the library before winter.",
    "We will open the reading room to every child in the district.",
    "We will keep the doors open late on Fridays.",
    "We will ask nothing in return.",
]
REPEAT_TERM = [
    "The library opened in 1911 with a single shelf of donated books.",
    "The library, according to the town records, was the first public building to have electric light.",
    "Library volunteers still run the Saturday story hour, although funding has always been uncertain.",
]
DISCONNECTED = ["The bell rang.", "Snow fell outside.", "Prices doubled overnight.", "A dog barked."]
LINKED = ["The bell rang.", "Then the snow fell.", "However, the bus came.", "Because of this, we waited."]
DENSE = ("Because the bridge had closed after the storm, the council, which had already spent its budget, "
         "decided that the repairs would wait until spring, although several residents objected.")
MIXED = """# Planning the trip

Rain came early that year. By the time the farmers had finished bringing in the last of the barley from the lower fields, the river had already risen past the old stone marker by the mill.

- a list item that runs on for a great many words so that it would be the longest sentence in the document by far if it counted
- short item

> A quoted passage that also runs on for a great many words, far longer than any prose sentence here, and it keeps going.

```
def f(x):
    return x + 1
```

Nobody was surprised. Grandmother said the swallows had warned us weeks before. She was often right.
"""


NUMBERS = "two three four five six seven eight nine ten eleven".split()
# Alternating short and long sentences.
ALTERNATING = [s for n in NUMBERS for s in (
    "It rained.",
    f"Then {n} tired farmers walked slowly along the muddy river bank toward the old mill before the evening "
    "storm arrived.")]
# A metrical passage: function and content monosyllables in strict alternation
# ("i WALK to TOWN and BUY the BREAD"), and the same words out of that order.
IAMBIC = ["I walk to town and buy the bread.", "We sit by fires and drink the wine.",
          "You climb the hill and see the sea.", "They sing a song and dance till dawn.",
          "She reads a book and bakes a cake.", "He rides his horse and feeds the dogs.",
          "We watch the stars and count the sheep.", "I paint the wall and fix the door.",
          "You write a note and mail it home.", "They plant the seeds and wait for rain."]
SCRAMBLED = [" ".join(sorted(s.rstrip(".").split(), key=lambda w: (len(w) < 4, w))) + "." for s in IAMBIC]
PROSE, HEADING, LIST_ITEM, QUOTATION, CODE = (cadence.TYPE_CODES[t] for t in
                                              ("prose", "heading", "list_item", "quotation", "code"))


def para(*sents):
    return " ".join(sents)


def doc(*paras):
    return "\n\n".join(paras)


def spans(m, key):
    p = m["patterns"][key]
    return list(zip(p["start"], p["end"]))


def row(m, k):
    return {f: v[k] for f, v in m["sentences"].items()}


def quote(text, m, k):
    return text[m["sentences"]["start"][k]:m["sentences"]["end"][k]]


class Columns(unittest.TestCase):
    def test_sentence_columns(self):
        text = doc(para("It rained; we stayed in, because the road (the only one) had flooded.", "This was new."),
                   "Then it stopped.")
        m = cadence.measure(text)
        S = m["sentences"]
        self.assertEqual(tuple(S), cadence.SENTENCE_FIELDS)
        self.assertEqual({len(v) for v in S.values()}, {3})
        s0, s1, s2 = (row(m, k) for k in range(3))
        self.assertEqual(quote(text, m, 0), "It rained; we stayed in, because the road (the only one) had flooded.")
        self.assertEqual(quote(text, m, 2), "Then it stopped.")
        self.assertEqual(s0["words"], 13)
        self.assertEqual(s0["pause_count"], 4)                       # ; , ( )
        self.assertEqual(s0["pause_positions"][0], round(2 / 13, 2))
        self.assertGreaterEqual(s0["relations"], 1)                  # because
        self.assertGreaterEqual(s2["relations"], 1)                  # then
        self.assertIsNone(s0["overlap_ratio"])
        self.assertIsNone(s0["opening_sim_prev"])
        self.assertIsNone(s0["skeleton_sim_prev"])
        self.assertTrue(s1["opens_with_reference"])
        self.assertEqual(S["type_code"], [PROSE] * 3)
        self.assertEqual(S["paragraph"], [0, 0, 1])
        self.assertEqual(S["is_paragraph_final"], [False, True, True])
        self.assertEqual(S["is_standalone"], [False, False, True])
        P = m["paragraphs"]
        self.assertEqual(tuple(P), cadence.PARAGRAPH_FIELDS)
        self.assertEqual((P["words"], P["sentences"], P["first_sentence"]), ([16, 3], [2, 1], [0, 2]))

    def test_opening_and_skeleton_similarity(self):
        m = cadence.measure(para("We will rebuild the library before winter.", "We will open the reading room.",
                                 "We could leave.", "Nobody came to the meeting that evening."))
        o = m["sentences"]["opening_sim_prev"]
        self.assertEqual(o[1:], [1.0, 0.5, 0.0])
        for v in m["sentences"]["skeleton_sim_prev"][1:]:
            self.assertTrue(0.0 <= v <= 1.0)

    def test_link_overlap(self):
        m = cadence.measure(para("The river flooded the valley.", "Rivers drain valleys slowly.", "Nothing else moved."))
        self.assertEqual(m["sentences"]["overlap_ratio"][1], round(2 / 3, 3))    # river, valley of river, drain, valley
        self.assertEqual(m["sentences"]["overlap_ratio"][2], 0.0)

    def test_numbers_only(self):
        text = doc(para(*VARIED[:4]), para(*REPEAT_TERM), para(*FLAT), "It failed.", para(*VARIED[4:]))
        m = cadence.measure(text)
        self.assertEqual(set(m), {"summary", "sentences", "paragraphs", "phrases", "patterns", "rhythm"})

        def strings(x):
            if isinstance(x, str):
                yield x
            elif isinstance(x, dict):
                for v in x.values():
                    yield from strings(v)
            elif isinstance(x, list):
                for v in x:
                    yield from strings(v)
        self.assertEqual(list(strings(m)), [])
        al = cadence.align(text, doc(para(*VARIED[:4]), para(*FLAT), para(*VARIED[4:])))
        self.assertEqual(list(strings(al)), [])
        self.assertFalse(hasattr(cadence, "to_html"))

    def test_compact(self):
        text = doc(*(para(*VARIED[i:i + 3]) for i in range(0, 12, 3)), para(*FLAT), para(*REPEAT_OPEN))
        m = cadence.measure(text)
        size = len(json.dumps(m, separators=(",", ":")))
        # a fixed part (rhythm, thresholds, counts) plus under 180 bytes a sentence
        self.assertLess(size, 2000 + 180 * m["summary"]["sentences"])


class Rhythm(unittest.TestCase):
    def test_word_stress(self):
        ws = cadence.word_stress
        self.assertEqual(ws("about", "ADP"), [0, 1])
        self.assertEqual(ws("table", "NOUN"), [1, 0])
        self.assertEqual(ws("the", "DET"), [0])
        self.assertEqual(ws("dog", "NOUN"), [1])
        self.assertEqual(ws("'s", "PART"), [])
        self.assertEqual(ws("n't", "PART", "did"), [0])
        self.assertEqual(ws("n't", "PART", "do"), [])
        self.assertEqual(ws(",", "PUNCT"), [])
        self.assertEqual(ws("38", "NUM"), [1])
        oov = ws("blorvingtonish", "ADJ")               # not in the dictionary: first syllable
        self.assertGreater(len(oov), 1)
        self.assertEqual(oov[0], 1)
        self.assertEqual(sum(oov), 1)

    def test_sentence_columns(self):
        text = para("The dog ran to the house, and then it slept.", "I waited.")
        S = cadence.measure(text)["sentences"]
        self.assertEqual(S["syllables"], [10, 3])
        self.assertEqual(S["final_stress_offset"], [0, 1])            # slept / WAIT-ed
        self.assertEqual(S["phrases"], [2, 1])
        self.assertEqual(S["phrase_start"], [0, 2])
        flat = cadence.measure(text)["phrases"]["syllables"]
        self.assertEqual(flat, [6, 4, 3])

    def test_metrical_passage_alternates(self):
        r = cadence.measure(para(*IAMBIC))["rhythm"]["beat"]
        self.assertGreater(r["alternation_share"]["value"], 0.9)
        self.assertGreater(r["alternation_share"]["z"], 3)
        self.assertLess(r["clash_rate"]["z"], -2)
        s = cadence.measure(para(*SCRAMBLED))["rhythm"]["beat"]
        self.assertLess(s["alternation_share"]["z"], 0)
        self.assertLess(s["alternation_share"]["value"], r["alternation_share"]["value"])
        self.assertEqual(s["syllables"], r["syllables"])              # the same words
        self.assertEqual(s["stresses"], r["stresses"])

    def test_null_is_deterministic(self):
        a = cadence.measure(para(*VARIED))["rhythm"]
        b = cadence.measure(para(*VARIED))["rhythm"]
        self.assertEqual(a, b)
        for lvl, key in (("beat", "clash_rate"), ("phrase", "phrase_contrast"), ("contour", "alternation")):
            self.assertEqual(set(a[lvl][key]), {"value", "null_mean", "z"})

    def test_landing(self):
        long = ("After the long winter the whole village gathered at the edge of the river to watch the ice break "
                "and drift away downstream.")
        text = doc(para("Rain came.", "Snow fell.", "Wind blew.", long), para("Rain came.", "Snow fell.", long),
                   para("It stopped."))
        m = cadence.measure(text)
        P = m["paragraphs"]
        self.assertGreater(P["final_ratio"][0], 5)
        self.assertEqual(P["initial_ratio"][0], 1.0 * P["initial_ratio"][0])
        self.assertIsNone(P["final_ratio"][2])                          # one sentence
        la = m["rhythm"]["landing"]
        self.assertEqual(la["paragraphs"], 2)
        self.assertGreater(la["final_ratio"]["value"], la["final_ratio"]["null_mean"])

    def test_end_weight_and_contrast(self):
        text = para(*[f"When the {n} came, we stayed at home and waited for the long bright evening to end."
                      for n in NUMBERS])
        ph = cadence.measure(text)["rhythm"]["phrase"]
        self.assertGreater(ph["end_weight"]["value"], 1)             # a short phrase, then a long one
        self.assertGreater(ph["phrase_contrast"]["value"], 40)
        self.assertEqual(sum(ph["endings"]), 1.0)

    def test_contour(self):
        m = cadence.measure(doc(para(*VARIED)), window=3)
        c = m["rhythm"]["contour"]
        n = m["summary"]["prose_sentences"]
        self.assertEqual(len(c["smooth"]), n)
        self.assertEqual(len(c["local_variation"]), n)
        self.assertEqual(c["sentence"], list(range(n)))
        S = m["sentences"]["syllables"]
        self.assertAlmostEqual(c["smooth"][1], round(sum(S[0:3]) / 3, 2))
        alt = cadence.measure(para(*ALTERNATING))["rhythm"]["contour"]["alternation"]
        self.assertLess(alt["value"], -0.5)
        self.assertLess(alt["z"], -2)


class Patterns(unittest.TestCase):
    def test_flat_stretch(self):
        m = cadence.measure(doc(para(*VARIED[:4]), para(*VARIED[4:6]), para(*FLAT), para(*VARIED[6:])))
        runs = spans(m, "flat_stretches")
        self.assertEqual(len(runs), 1)
        a, b = runs[0]
        flat_ids = {k for k, p in enumerate(m["sentences"]["paragraph"]) if p == 2}
        self.assertGreaterEqual(b - a + 1, cadence.FLAT_RUN)
        self.assertTrue(set(range(a, b + 1)) <= flat_ids)
        self.assertAlmostEqual(m["patterns"]["flat_stretch_share"], round((b - a + 1) / m["summary"]["sentences"], 3))

    def test_no_flat_stretch_on_varied_control(self):
        m = cadence.measure(doc(para(*VARIED[:4]), para(*VARIED[4:8]), para(*VARIED[8:])))
        self.assertEqual(spans(m, "flat_stretches"), [])
        self.assertEqual(m["patterns"]["flat_stretch_share"], 0.0)

    def test_repeated_opening_is_structure(self):
        m = cadence.measure(doc(para(*VARIED[:4]), para(*REPEAT_OPEN), para(*VARIED[4:8])))
        rs = m["patterns"]["repeated_structure"]
        self.assertEqual(len(rs["start"]), 1)
        self.assertEqual(rs["by"], [cadence.BY_OPENING])
        self.assertEqual(rs["end"][0] - rs["start"][0] + 1, 4)
        self.assertEqual(m["patterns"]["counts"]["repeated_terminology"], 0)
        for k in range(rs["start"][0] + 1, rs["end"][0] + 1):
            self.assertEqual(m["sentences"]["opening_sim_prev"][k], 1.0)

    def test_repeated_terminology_is_distinct(self):
        text = doc(para(*VARIED[:4]), para(*REPEAT_TERM), para(*VARIED[4:8]))
        m = cadence.measure(text)
        rt = m["patterns"]["repeated_terminology"]
        self.assertEqual(len(rt["start"]), 1)
        self.assertEqual(text[rt["term_start"][0]:rt["term_end"][0]], "library")
        self.assertEqual(rt["end"][0] - rt["start"][0] + 1, 3)
        self.assertEqual(m["patterns"]["counts"]["repeated_structure"], 0)

    def _run_doc(self, run):
        return doc(para(VARIED[1], VARIED[3], VARIED[5]), para(*run), para(VARIED[7], VARIED[9], VARIED[11]),
                   para(FLAT[0], FLAT[2]))

    def test_disconnected_run(self):
        m = cadence.measure(self._run_doc(DISCONNECTED))
        runs = spans(m, "disconnected_runs")
        self.assertEqual(len(runs), 1)
        a, b = runs[0]
        self.assertEqual(set(m["sentences"]["paragraph"][a:b + 1]), {1})
        self.assertGreaterEqual(b - a + 1, 3)

    def test_linked_short_sentences_are_not_disconnected(self):
        m = cadence.measure(self._run_doc(LINKED))
        self.assertEqual(spans(m, "disconnected_runs"), [])
        S = m["sentences"]
        run = [k for k, p in enumerate(S["paragraph"]) if p == 1]
        self.assertTrue(all(S["relations"][k] for k in run[1:]))

    def test_dense_relations(self):
        context = [s for s in VARIED if len(s.split()) < 20]
        text = doc(para(*context[:5]), para(DENSE), para(*context[5:]), para(*FLAT[:3]))
        m = cadence.measure(text)
        d = m["patterns"]["dense_relations"]
        self.assertEqual(len(d["sentence"]), 1)
        self.assertEqual(quote(text, m, d["sentence"][0]), DENSE)
        self.assertGreaterEqual(d["relations"][0], 5)       # because, after, which, that, until, although

    def test_standalone_emphasis_point(self):
        text = doc(para(VARIED[1], VARIED[3]), "It failed.", para(VARIED[5], VARIED[9]), para(*FLAT[:4]))
        m = cadence.measure(text)
        e = m["patterns"]["emphasis_points"]
        hits = [i for i, k in enumerate(e["sentence"]) if quote(text, m, k) == "It failed."]
        self.assertEqual(len(hits), 1)
        k = e["sentence"][hits[0]]
        self.assertTrue(e["shorter_than_neighbours"][hits[0]])
        self.assertTrue(m["sentences"]["is_standalone"][k] and m["sentences"]["is_paragraph_final"][k])

    def test_thresholds_are_the_documents_own(self):
        m = cadence.measure(doc(para(*VARIED)))
        L = sorted(m["sentences"]["words"])
        self.assertEqual(m["patterns"]["thresholds"]["median"], (L[5] + L[6]) / 2)
        self.assertEqual(m["summary"]["prose_length_percentiles"]["median"], (L[5] + L[6]) / 2)

    def test_too_few_sentences(self):
        m = cadence.measure(para(*VARIED[:4]))
        self.assertFalse(m["patterns"]["computed"])
        self.assertEqual(spans(m, "flat_stretches"), [])


class ContentTypes(unittest.TestCase):
    def test_markers_excluded_from_statistics(self):
        m = cadence.measure(MIXED)
        self.assertEqual(m["summary"]["type_counts"], [2, 1, 2, 1, 1, 0])
        codes = m["sentences"]["type_code"]
        self.assertEqual(codes[0], HEADING)
        self.assertTrue(codes.index(LIST_ITEM) < codes.index(QUOTATION) < codes.index(CODE))
        prose = [k for k, c in enumerate(codes) if c == PROSE]
        self.assertEqual(len(prose), 5)
        self.assertEqual(m["summary"]["prose_sentences"], 5)
        self.assertEqual(m["rhythm"]["contour"]["sentence"], prose)
        self.assertLessEqual(m["summary"]["prose_length_percentiles"]["p90"],
                             max(m["sentences"]["words"][k] for k in prose))
        for k in m["patterns"]["emphasis_points"]["sentence"]:
            self.assertEqual(codes[k], PROSE)

    def test_quotation_paragraph_and_plain_title(self):
        text = doc("The Long Winter", para(*VARIED[:3]),
                   "“We will not leave,” she said, “not while the river is still rising "
                   "and the road is under water.”", para(*VARIED[3:6]))
        self.assertEqual(cadence.measure(text)["paragraphs"]["type_code"], [PROSE + 1, PROSE, QUOTATION, PROSE])

    def test_one_line_paragraphs(self):
        m = cadence.measure("First line here.\nSecond line here.\nThird line here.")
        self.assertEqual(m["summary"]["paragraphs"], 3)
        self.assertTrue(m["summary"]["one_line_paragraphs"])


class Align(unittest.TestCase):
    A = para(*VARIED[:3])
    B = para(*VARIED[3:6])
    C = para(*VARIED[6:9])
    ST = cadence.STATUS_CODES

    def test_inserted_paragraph(self):
        al = cadence.align(doc(self.A, self.B, self.C), doc(self.A, para(*FLAT[:3]), self.B, self.C))
        P = al["passages"]
        self.assertEqual(P["status"], [self.ST[s] for s in ("unchanged", "inserted", "unchanged", "unchanged")])
        self.assertEqual((P["b_sent_start"][1], P["b_type"][1]), (-1, -1))
        self.assertEqual(P["a_sent_end"][1] - P["a_sent_start"][1] + 1, 3)
        self.assertEqual({len(v) for v in P.values()}, {4})

    def test_paragraph_to_list(self):
        al = cadence.align(doc(self.A, "Pack light. Bring water, a map and a charged phone.", self.C),
                           doc(self.A, "- Pack light.\n- Bring water.\n- Bring a map.\n- Bring a charged phone.",
                               self.C))
        P = al["passages"]
        k = P["status"].index(self.ST["converted"])
        self.assertEqual((P["b_type"][k], P["a_type"][k]), (PROSE, LIST_ITEM))
        self.assertEqual(P["b_sent_end"][k] - P["b_sent_start"][k] + 1, 2)
        self.assertEqual(P["a_sent_end"][k] - P["a_sent_start"][k] + 1, 4)
        self.assertEqual(P["a_items"][k], 4)

    def test_split_paragraph(self):
        al = cadence.align(doc(self.A, para(*VARIED[3:7])), doc(self.A, para(*VARIED[3:5]), para(*VARIED[5:7])))
        P = al["passages"]
        self.assertEqual(P["status"], [self.ST["unchanged"], self.ST["split"]])
        self.assertEqual((P["b_parts"][1], P["a_parts"][1]), (1, 2))

    def test_types_match_only_their_own(self):
        P = cadence.align(doc("# Rain", self.A, self.B), doc(self.A, "# Rain", self.B))["passages"]
        for tb, ta in zip(P["b_type"], P["a_type"]):
            if tb >= 0 and ta >= 0:
                self.assertEqual(tb, ta)


class TermRuns(unittest.TestCase):
    # Pride and Prejudice, ch. XX (public domain). A run of repeated terminology
    # where a later pair shares a noun ("collins") the run's first sentence
    # lacks; looking that noun up in the first sentence raised KeyError.
    AUSTEN = (
        "Mr. Collins was not left long to the silent contemplation of his successful love; "
        "for Mrs. Bennet, having dawdled about in the vestibule to watch for the end of the "
        "conference, no sooner saw Elizabeth open the door and with quick step pass her towards "
        "the staircase, than she entered the breakfast-room, and congratulated both him and "
        "herself in warm terms on the happy prospect of their nearer connection. Mr. Collins "
        "received and returned these felicitations with equal pleasure, and then proceeded to "
        "relate the particulars of their interview, with the result of which he trusted he had "
        "every reason to be satisfied, since the refusal which his cousin had steadfastly given "
        "him would naturally flow from her bashful modesty and the genuine delicacy of her "
        "character. This information, however, startled Mrs. Bennet: she would have been glad "
        "to be equally satisfied that her daughter had meant to encourage him by protesting "
        "against his proposals, but she dared not believe it, and could not help saying so. "
        "“But depend upon it, Mr. Collins,” she added, “that Lizzy shall be "
        "brought to reason. I will speak to her about it myself directly. She is a very "
        "headstrong, foolish girl, and does not know her own interest; but I will _make_ her "
        "know it.” “Pardon me for interrupting you, madam,” cried Mr.")

    def test_term_span_comes_from_the_first_sentence(self):
        text = "[Illustration] CHAPTER XX. [Illustration] " + self.AUSTEN
        rt = cadence.measure(text)["patterns"]["repeated_terminology"]
        for s, e in zip(rt["term_start"], rt["term_end"]):
            self.assertTrue(text[s:e].isalpha())


class Cli(unittest.TestCase):
    def test_cli_json(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.txt"
            f.write_text(doc(para(*VARIED[:4]), para(*FLAT), para(*VARIED[4:])), encoding="utf-8")
            env = {"PYTHONPATH": str(ROOT / "src")}
            r = subprocess.run([sys.executable, "-m", "proseweave", "cadence", str(f), "--json", "--window", "4"],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            j = json.loads(r.stdout)
            self.assertEqual(j["rhythm"]["contour"]["window"], 4)
            self.assertEqual(j["patterns"]["counts"]["flat_stretches"], 1)
            r = subprocess.run([sys.executable, "-m", "proseweave", "cadence", str(f)],
                               capture_output=True, text=True, env=env)
            self.assertIn("beat alternation", r.stdout)


if __name__ == "__main__":
    unittest.main()
