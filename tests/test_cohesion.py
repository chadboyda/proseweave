import unittest

import _path  # noqa: F401
from proseweave import analysis
from proseweave import cohesion as c


def tok(word, cls):
    return c.Tok(word, word, cls, "det" if word in c.DEMONSTRATIVES else None, False)


def lists():
    """One paragraph: 'the cat sat' / 'the cat ran' / 'a dog ran'."""
    s1 = [tok("the", "DET"), tok("cat", "NOUN"), tok("sat", "VERB")]
    s2 = [tok("the", "DET"), tok("cat", "NOUN"), tok("ran", "VERB")]
    s3 = [tok("a", "DET"), tok("dog", "NOUN"), tok("ran", "VERB")]
    return c.Lists([[s1, s2, s3]])


class Formulas(unittest.TestCase):
    def test_ttr(self):
        f = c.ttr_family(lists())
        self.assertAlmostEqual(f["lemma_ttr"], 6 / 9)
        self.assertAlmostEqual(f["noun_ttr"], 2 / 3)
        self.assertAlmostEqual(f["lexical_density_tokens"], 6 / 9)

    def test_adjacent_overlap(self):
        o = c.overlap_family(lists())
        # the,cat shared by s1/s2; ran by s2/s3: 3 overlaps over 6 types, 2 pairs.
        self.assertAlmostEqual(o["adjacent_overlap_all_sent"], 0.5)
        self.assertAlmostEqual(o["adjacent_overlap_all_sent_div_seg"], 1.5)
        self.assertAlmostEqual(o["adjacent_overlap_binary_all_sent"], 1.0)
        self.assertAlmostEqual(o["adjacent_overlap_2_all_sent"], 2 / 3)
        self.assertAlmostEqual(o["adjacent_overlap_noun_sent"], 0.5)
        self.assertAlmostEqual(o["adjacent_overlap_cw_sent"], 0.5)
        # a single paragraph has no adjacent pair
        self.assertEqual(o["adjacent_overlap_all_para"], 0.0)

    def test_overlap_raw(self):
        self.assertEqual(c.overlap([["a"]]), (0.0,) * 6)

    def test_mattr(self):
        self.assertAlmostEqual(c.mattr(list("aabb"), w=2), 2 / 3)
        self.assertAlmostEqual(c.mattr(list("aab"), w=3), 2 / 3)   # too short: plain TTR

    def test_connectives_and_givenness(self):
        L = lists()
        cc = c.closed_connectives(L)
        self.assertAlmostEqual(cc["determiners"], 3 / 9)
        self.assertEqual(cc["conjunctions"], 0.0)
        g = c.givenness(L)
        self.assertEqual(g["pronoun_density"], 0.0)
        # cat and ran each appear twice: 4 repeated content tokens over 9 words
        self.assertAlmostEqual(g["repeated_content_lemmas"], 4 / 9)

    def test_mtld(self):
        self.assertEqual(analysis.mtld(["a"] * 49), 0.0)
        self.assertAlmostEqual(analysis.mtld(["a"] * 50), 2.0)


if __name__ == "__main__":
    unittest.main()
