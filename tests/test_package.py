import json
import os
import subprocess
import sys
import unittest

import _path
import catalog
import proseweave
from proseweave import analysis

TEXT = ("The cat sat on the mat. It was happy.\n\n"
        "Then the dog came home and barked loudly at the cat.")

BASIC = {"n_tokens", "n_types", "n_sentences", "n_paragraphs", "type_token_ratio", "mtld_score",
         "sent_len_mean", "sent_len_std", "sent_len_cv", "flesch_reading_ease", "flesch_kincaid_grade",
         "automated_readability_index", "text_length", "word_count", "dep_distance_mean",
         "dep_distance_std", "noun_ratio", "verb_ratio", "adj_ratio", "adv_ratio",
         "semantic_cohesion_mean", "semantic_cohesion_std", "semantic_cohesion_min", "semantic_cohesion_max",
         "paragraph_cohesion_mean", "paragraph_cohesion_std", "zipf_mean", "zipf_std"}
# Needs Jev: the judge-scale easability parts.
JEV_ONLY = {"narrativity", "word_concreteness", "referential_cohesion",
            "deep_cohesion", "overall_quality"}


class NoKey(unittest.TestCase):
    def test_basic(self):
        b = proseweave.Analysis(TEXT, None).basic()
        self.assertEqual(set(b), BASIC)
        self.assertEqual(b["n_tokens"], 10)
        self.assertEqual(b["n_types"], 9)
        self.assertEqual(b["n_sentences"], 3)
        self.assertEqual(b["n_paragraphs"], 2)
        self.assertEqual(b["word_count"], 20)
        self.assertEqual(b["text_length"], len(TEXT))
        self.assertAlmostEqual(b["type_token_ratio"], 0.9)
        self.assertEqual(b["mtld_score"], 0.0)
        self.assertGreater(b["flesch_reading_ease"], 60)
        for v in b.values():
            self.assertIsInstance(v, (int, float))

    def test_properties_without_key(self):
        p = proseweave.Analysis(TEXT, None).properties()
        self.assertLessEqual(BASIC | {"syntactic_simplicity"}, set(p))
        self.assertTrue(0 <= p["syntactic_simplicity"] <= 100)
        # the tagger supplies word classes, so the cohesion indices are local
        for k in ("adjacent_overlap_cw_sent", "addition", "all_causal", "syn_overlap_sent_noun", "lsa_1_all_sent",
                  "referential_cohesion_construct", "deep_cohesion_construct", "zipf_mean"):
            self.assertIn(k, p)
        self.assertFalse(JEV_ONLY & set(p))
        for v in p.values():
            self.assertIsInstance(v, (int, float))

    def test_exports(self):
        for name in ("Analysis", "profile", "compare", "compare_source", "Jev"):
            self.assertTrue(hasattr(proseweave, name), name)
        self.assertEqual(proseweave.__version__, "0.2.0")


class Validation(unittest.TestCase):
    def test_covers_every_property(self):
        v = json.loads(analysis.VALIDATION.read_text(encoding="utf-8"))
        props = set(catalog.all_props())
        self.assertEqual(len(props), 204)     # 202 scored against references, 2 construct
        self.assertEqual(set(v), props)
        for p, x in v.items():
            self.assertIn("valid", x, p)
            self.assertIn("family", x, p)
            if x["family"] == "construct":    # defined by formula; no external reference
                self.assertFalse(x["valid"], p)
                self.assertIn("no external reference", x["note"], p)
                continue
            # valid means it passed on both validation corpora
            passed = [x[c].get("rho", 0) >= 0.80 and x[c].get("lower90", 0) >= 0.70 for c in ("private", "open")]
            self.assertEqual(x["valid"], all(passed), p)
        self.assertEqual(sum(x["family"] == "construct" for x in v.values()), 2)
        self.assertEqual(sum(x["valid"] for x in v.values()), 189)
        self.assertEqual(set(analysis.trusted()), {p for p, x in v.items() if x["valid"]} -
                         {p for p, x in v.items() if x["family"] in analysis.SKIP_FAMILIES})

    def test_local_properties_are_catalogued(self):
        self.assertLessEqual(set(proseweave.Analysis(TEXT, None).properties()), set(catalog.all_props()))

    def test_full_property_set_is_catalogued(self):
        class SilentJev:
            """Answers nothing, offline, so every property name is still emitted."""
            def ask_many(self, jobs):
                return [{} for _ in jobs]

        p = proseweave.Analysis(TEXT, SilentJev()).properties()
        self.assertEqual(set(p), set(catalog.all_props()))


class CLI(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ, PYTHONPATH=str(_path.ROOT / "src"))
        return subprocess.run([sys.executable, "-m", "proseweave", *args], env=env,
                              capture_output=True, text=True, timeout=60)

    def test_help(self):
        r = self.run_cli("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for cmd in ("analyze", "profile", "compare", "source", "setup", "check"):
            self.assertIn(cmd, r.stdout)

    def test_no_jev_default_command(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(TEXT)
        try:
            r = self.run_cli(f.name, "--no-jev", "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(set(json.loads(r.stdout)), set(proseweave.Analysis(TEXT, None).properties()))
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
