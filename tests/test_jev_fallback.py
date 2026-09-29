import contextlib
import io
import unittest
import urllib.error
from unittest import mock

import _path  # noqa: F401
import proseweave
from proseweave import analysis, jev

TEXT = ("The cat sat on the mat because it was warm. Then the dog came home and barked at the cat.\n\n"
        "Since the rain had stopped, they both went outside to play in the garden.")


def _no_credits(req, timeout=None):
    body = io.BytesIO(b'{"detail":{"error_type":"billing_error","message":"no credits"}}')
    raise urllib.error.HTTPError(req.full_url, 402, "Payment Required", {}, body)


class NoCredits(unittest.TestCase):
    def setUp(self):
        self.saved = jev.CACHE_DIR
        jev.CACHE_DIR = None
        analysis._WARNED.clear()

    def tearDown(self):
        jev.CACHE_DIR = self.saved

    def test_402_is_jev_unavailable(self):
        j = jev.Jev(key="test")
        with mock.patch("urllib.request.urlopen", _no_credits):
            with self.assertRaises(jev.JevUnavailable) as cm:
                j.ask("state", {"q": {"type": "noul", "instructions": "?"}})
        self.assertIn("402", str(cm.exception))
        self.assertIn("credits", str(cm.exception))

    def test_analysis_falls_back_to_local_routes(self):
        j = jev.Jev(key="test")
        err = io.StringIO()
        with mock.patch("urllib.request.urlopen", _no_credits), contextlib.redirect_stderr(err):
            got = proseweave.Analysis(TEXT, j).properties()
            again = proseweave.Analysis(TEXT, j).properties()
        self.assertEqual(got, proseweave.Analysis(TEXT, None).properties())
        self.assertEqual(again, got)
        lines = err.getvalue().splitlines()
        self.assertEqual(len(lines), 1)              # warned once, on one line
        self.assertIn("local routes", lines[0])

    def test_source_comparison_falls_back_to_tables(self):
        j = jev.Jev(key="test")
        with mock.patch("urllib.request.urlopen", _no_credits), contextlib.redirect_stderr(io.StringIO()):
            res = proseweave.compare_source(TEXT, TEXT.replace("cat", "kitten"), j)
        self.assertIn("mag_news_uni_keywords_percentage", res)
        self.assertIn("source_similarity_lsa", res)


if __name__ == "__main__":
    unittest.main()
