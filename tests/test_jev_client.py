"""The Jev client's request shape, image assets and usage hook, with the network mocked out."""
import base64
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import _path  # noqa: F401
from proseweave import jev


class _Resp:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# origin/main's _cache_key("s", {"q": {}}) with model "test"
OLD_KEY = "f787d869226cce817866e8f90b72a28922ee0973320a33a832c08127d4376b58"
RESPONSE = {"model": "jev-x", "answers": {"q": {"noul": 0.8}}, "usage": {"input_tokens": 1234, "output_tokens": 9}}


class Client(unittest.TestCase):
    def setUp(self):
        self.sent = []

        def fake(req, timeout=None):
            self.sent.append(req)
            return _Resp(RESPONSE)

        p = mock.patch.object(jev.urllib.request, "urlopen", side_effect=fake)
        p.start()
        self.addCleanup(p.stop)
        saved = jev.CACHE_DIR
        jev.CACHE_DIR = None
        self.addCleanup(setattr, jev, "CACHE_DIR", saved)

    def headers(self, req):
        return {k.lower(): v for k, v in req.header_items()}

    def test_text_request_has_user_agent_and_no_image_header(self):
        j = jev.Jev(key="k")
        self.assertEqual(j.ask("state", {"q": {"type": "noul"}}), RESPONSE["answers"])
        h = self.headers(self.sent[0])
        self.assertEqual(h["user-agent"], jev.USER_AGENT)
        self.assertNotIn(jev.IMAGE_HEADER.lower(), h)
        self.assertNotIn("assets", json.loads(self.sent[0].data))

    def test_assets_go_in_the_body_with_the_image_header(self):
        j = jev.Jev(key="k", user_agent="test-ua")
        ref = jev.new_ref()
        asset = jev.image_asset(b"\x89PNG-bytes", "PNG")
        r = j.ask_full({"shot": ref}, {"q": {"type": "noul"}}, assets={ref: asset})
        body = json.loads(self.sent[0].data)
        self.assertEqual(body["assets"][ref]["format"], "png")
        self.assertEqual(base64.b64decode(body["assets"][ref]["data_base64"]), b"\x89PNG-bytes")
        h = self.headers(self.sent[0])
        self.assertEqual(h[jev.IMAGE_HEADER.lower()], "true")
        self.assertEqual(h["user-agent"], "test-ua")
        self.assertEqual(r["usage"]["input_tokens"], 1234)
        self.assertFalse(r["cached"])
        self.assertGreaterEqual(r["latency_s"], 0.0)

    def test_on_usage_gets_the_provider_usage_once_per_request(self):
        events = []
        j = jev.Jev(key="k", on_usage=events.append)
        j.ask("s", {"q": {}}, tag="t1")
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e["input_tokens"], 1234)
        self.assertEqual(e["usage"], RESPONSE["usage"])
        self.assertEqual((e["model"], e["tag"], e["questions"], e["images"]), ("jev-x", "t1", 1, 0))

    def test_on_usage_error_stops_the_caller(self):
        def stop(_):
            raise RuntimeError("budget")
        j = jev.Jev(key="k", on_usage=stop)
        with self.assertRaises(RuntimeError):
            j.ask("s", {"q": {}})

    def test_image_asset_rejects_unknown_formats(self):
        self.assertEqual(jev.image_asset(b"x", "jpeg")["format"], "jpg")
        with self.assertRaises(ValueError):
            jev.image_asset(b"x", "gif")

    def test_cache_key_covers_assets_and_hits_skip_the_hook(self):
        with tempfile.TemporaryDirectory() as d:
            jev.CACHE_DIR = Path(d)
            events = []
            j = jev.Jev(key="k", on_usage=events.append)
            a1 = {"r": jev.image_asset(b"one")}
            a2 = {"r": jev.image_asset(b"two")}
            j.ask({"shot": "r"}, {"q": {}}, assets=a1)
            hit = j.ask_full({"shot": "r"}, {"q": {}}, assets=a1)
            self.assertTrue(hit["cached"])
            j.ask({"shot": "r"}, {"q": {}}, assets=a2)      # other image: a new request
            self.assertEqual((len(self.sent), len(events)), (2, 2))
            # the text-only key is the one origin/main computed, so old caches stay valid
            j.model = "test"
            self.assertEqual(j._cache_key("s", {"q": {}}), OLD_KEY)

    def test_ref_from_bytes_is_stable(self):
        self.assertEqual(jev.new_ref(b"png"), jev.new_ref(b"png"))
        self.assertNotEqual(jev.new_ref(b"png"), jev.new_ref(b"other"))
        self.assertNotEqual(jev.new_ref(), jev.new_ref())

    def test_paid_answer_is_cached_even_when_the_hook_stops(self):
        with tempfile.TemporaryDirectory() as d:
            jev.CACHE_DIR = Path(d)

            def stop(_):
                raise RuntimeError("budget")
            j = jev.Jev(key="k", on_usage=stop)
            with self.assertRaises(RuntimeError):
                j.ask("s", {"q": {}})
            self.assertEqual(j._cache_get("s", {"q": {}}), RESPONSE["answers"])

    def test_ask_many_stops_sending_after_a_hook_error(self):
        def stop(_):
            raise RuntimeError("budget")
        # the second request holds the single worker until the main thread has had time to cancel the queue,
        # so the bound does not depend on thread scheduling
        sent, release = [], threading.Event()

        def slow(req, timeout=None):
            sent.append(req)
            if len(sent) > 1:
                release.wait(1.0)
            return _Resp(RESPONSE)
        j = jev.Jev(key="k", on_usage=stop, workers=1)
        with mock.patch.object(jev.urllib.request, "urlopen", side_effect=slow):
            with self.assertRaises(RuntimeError):
                j.ask_many([(f"s{i}", {"q": {}}) for i in range(20)])
        release.set()
        self.assertLessEqual(len(sent), 2)


if __name__ == "__main__":
    unittest.main()
