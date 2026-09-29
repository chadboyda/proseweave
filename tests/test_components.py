import unittest

import _path  # noqa: F401
from proseweave import Analysis, connectives, magnews, syntax
from proseweave import text as tk


class Parser(unittest.TestCase):
    def test_model_loads(self):
        tagger, segmenter, parser = syntax.models()
        self.assertIn("NN", tagger.model.classes)
        self.assertGreater(len(parser.model.keys), 1000)

    def test_parse_short_text(self):
        toks = syntax.parse("The old dog slept in the sun. It woke at noon.")
        words = [t for t in toks if not t.is_space]
        self.assertEqual([t.text for t in words][:4], ["The", "old", "dog", "slept"])
        self.assertEqual(sum(t.sent_start for t in words), 2)
        by_text = {t.text: i for i, t in enumerate(toks)}
        self.assertEqual(toks[by_text["dog"]].head, by_text["slept"])      # subject -> verb
        self.assertEqual(toks[by_text["old"]].head, by_text["dog"])        # adjective -> noun
        self.assertEqual(toks[by_text["slept"]].head, by_text["slept"])    # root
        d = syntax.dep_distances(toks, tk.stop_words())
        self.assertTrue(d and all(x > 0 for x in d))

    def test_dependency_properties(self):
        d = Analysis("The old dog slept in the sun. It woke at noon.", None).dependency()
        self.assertGreater(d["dep_distance_mean"], 0)
        self.assertGreaterEqual(d["dep_distance_std"], 0)


class Connectives(unittest.TestCase):
    TEXT = ("We stayed inside because it rained. In order to stay dry, we also closed the windows. "
            "However, the roof leaked.")

    def test_toy_sentence(self):
        L = Analysis(self.TEXT, None).cohesion_lists()
        senses = connectives.senses_local(L.sents)
        count = lambda ix: connectives.count(L.sents, ix, senses)  # noqa: E731
        self.assertEqual(count("reason_and_purpose"), 2)     # because, in order to
        self.assertEqual(count("positive_intentional"), 1)   # in order to
        self.assertEqual(count("addition"), 1)               # also
        self.assertEqual(count("opposition"), 1)             # however

    def test_longest_item_wins_once(self):
        L = Analysis("She left in order to rest.", None).cohesion_lists()
        # "in order to" is one purpose connective, not "in order to" plus "to"
        self.assertEqual(connectives.count(L.sents, "positive_intentional", None), 1)

    def test_every_index_is_defined(self):
        for ix, spec in connectives.inventory()["indices"].items():
            for g in spec["groups"] + spec.get("plus", []):
                self.assertIn(g, connectives.inventory()["groups"], ix)


class Apostrophes(unittest.TestCase):
    def test_curly_and_straight_tokenize_alike(self):
        curly = "It’s ‘fine’, isn’t it? We can’t, and they won’t."
        self.assertEqual(tk.tokenize(curly), tk.tokenize(curly.replace("’", "'").replace("‘", "'")))
        self.assertEqual(tk.tokenize("isn’t")[-1], "n't")

    def test_properties_do_not_depend_on_apostrophe_style(self):
        curly = "She didn’t know. The dog’s bowl was empty, so she’d fill it."
        a = Analysis(curly, None).properties()
        b = Analysis(curly.replace("’", "'"), None).properties()
        self.assertEqual(a, b)

    def test_keyness_tables(self):
        self.assertEqual(magnews.per_million("uni", "don't"), magnews.per_million("uni", "don’t"))
        self.assertIsNotNone(magnews.per_million("uni", "the"))


if __name__ == "__main__":
    unittest.main()
