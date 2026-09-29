import unittest

import _path  # noqa: F401
from proseweave import text as tk


class Tokenize(unittest.TestCase):
    def test_contractions_punctuation_abbreviations(self):
        self.assertEqual(tk.tokenize("Don't stop, Mr. Smith!"),
                         ["Do", "n't", "stop", ",", "Mr.", "Smith", "!"])

    def test_special_negations(self):
        self.assertEqual(tk.tokenize("I can't. We won't."),
                         ["I", "ca", "n't", ".", "We", "wo", "n't", "."])

    def test_hyphens_and_brackets(self):
        self.assertEqual(tk.tokenize("well-known (really)."),
                         ["well", "-", "known", "(", "really", ")", "."])


class Split(unittest.TestCase):
    def test_sentences_respect_abbreviations(self):
        s = tk.sentences(tk.tokenize("It rained. We left early. Mr. Smith stayed."))
        self.assertEqual(s, [["It", "rained", "."], ["We", "left", "early", "."],
                             ["Mr.", "Smith", "stayed", "."]])

    def test_paragraphs(self):
        self.assertEqual(tk.paragraphs("a\n\nb\nc"), ["a", "b\nc"])
        self.assertEqual(tk.paragraphs("a\n\nb\nc", single_newline=True), ["a", "b", "c"])

    def test_parse(self):
        d = tk.parse("One. Two.\n\nThree.")
        self.assertEqual(len(d.paragraphs), 2)
        self.assertEqual(len(d.sentences), 3)
        self.assertEqual(d.tokens[0], "One")


class Lemmas(unittest.TestCase):
    def test_spot_checks(self):
        for word, cls, lemma in [("running", "VERB", "run"), ("mice", "NOUN", "mouse"),
                                 ("cats", "NOUN", "cat"), ("was", "VERB", "be"),
                                 ("London", "PROPN", "London")]:
            self.assertEqual(tk.lemmatize(word, cls), lemma, word)

    def test_closed_class(self):
        self.assertEqual(tk.closed_class("The"), "DET")
        self.assertEqual(tk.closed_class("they"), "PRON")
        self.assertIsNone(tk.closed_class("dog"))


if __name__ == "__main__":
    unittest.main()
