import tempfile
import threading
import unittest
from pathlib import Path

import _path  # noqa: F401
from proseweave import jev


class Cache(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.saved = jev.CACHE_DIR
        jev.CACHE_DIR = Path(self.dir.name)
        self.j = jev.Jev.__new__(jev.Jev)     # no key needed for the cache
        self.j.model = "test"

    def tearDown(self):
        jev.CACHE_DIR = self.saved
        self.dir.cleanup()

    def test_concurrent_put_get_one_key(self):
        state, qs = "s", {"q": {"type": "noul", "instructions": "?"}}
        answers = {"q": {"value": "x" * 200_000}}      # large enough that a write takes a while
        errors = []

        def worker(put):
            try:
                for _ in range(30):
                    if put:
                        self.j._cache_put(state, qs, answers)
                    else:
                        got = self.j._cache_get(state, qs)
                        if got is not None and got != answers:
                            errors.append("partial read")
            except Exception as e:     # noqa: BLE001
                errors.append(repr(e))

        threads = [threading.Thread(target=worker, args=(i % 2 == 0,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.j._cache_get(state, qs), answers)
        self.assertEqual([p.suffix for p in Path(self.dir.name).iterdir()], [".json"])

    def test_partial_file_is_a_miss(self):
        state, qs = "s", {"q": {}}
        f = Path(self.dir.name) / (self.j._cache_key(state, qs) + ".json")
        f.write_text('{"q": {"val')
        self.assertIsNone(self.j._cache_get(state, qs))


if __name__ == "__main__":
    unittest.main()
