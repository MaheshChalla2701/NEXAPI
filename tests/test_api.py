import dataclasses
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from backend import server
from backend.analyst import external, local_engine
from backend.config import load_settings
from pipeline import build_db


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        db = Path(cls.tmp.name) / "app.db"
        build_db.build("mock", db, {})
        cls.settings = dataclasses.replace(
            load_settings(), host="127.0.0.1", port=0, db_path=db, static_dir=Path(cls.tmp.name) / "dist",
            external_enabled=False, anthropic_api_key=None)
        cls.httpd = server.make_server(cls.settings)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, json.load(r)

    def post(self, path, payload, content_type="application/json"):
        req = urllib.request.Request(self.base + path, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": content_type})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def test_every_page_endpoint_returns_meta_and_data(self):
        for path in ("/api/overview", "/api/bridge", "/api/onboarding", "/api/pricing", "/api/referrals",
                     "/api/retention", "/api/data-quality", "/api/filters"):
            status, body = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertTrue(body["meta"]["is_mock"], path)
            self.assertIn("data", body, path)

    def test_bridge_endpoint_reconciles(self):
        _, body = self.get("/api/bridge")
        self.assertAlmostEqual(body["data"]["reconciliation"]["difference_pp"], 0.0, places=6)

    def test_invalid_filter_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/retention?segment=bogus")
        self.assertEqual(ctx.exception.code, 400)

    def test_unknown_endpoint_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/nope")
        self.assertEqual(ctx.exception.code, 404)

    def test_status_defaults_to_local(self):
        _, body = self.get("/api/analyst/status")
        self.assertEqual(body["default_mode"], "local")
        self.assertFalse(body["external_enabled"])

    def test_public_settings_never_contain_the_key(self):
        configured = dataclasses.replace(self.settings, external_enabled=True, anthropic_api_key="sk-test-SECRET")
        view = json.dumps(configured.public_view())
        self.assertTrue(configured.external_ready)
        self.assertNotIn("SECRET", view)

    def test_analyst_answers_supported_questions_locally(self):
        for s in local_engine.SUGGESTIONS:
            status, body = self.post("/api/analyst/ask", {"question": s["question"]})
            self.assertEqual(status, 200, s["question"])
            self.assertEqual(body["mode"], "local")
            self.assertEqual(body["intent"], s["intent"], s["question"])
            self.assertTrue(body["answered"], s["question"])
            self.assertIn("MOCK", " ".join(body["notices"]))

    def test_analyst_refuses_unsupported_question(self):
        _, body = self.post("/api/analyst/ask", {"question": "What will the weather be tomorrow?"})
        self.assertFalse(body["answered"])
        self.assertEqual(body["intent"], "unsupported")
        self.assertTrue(body["related"])

    def test_external_mode_falls_back_when_not_configured(self):
        _, body = self.post("/api/analyst/ask", {"question": "What drove the revenue change?", "mode": "external"})
        self.assertEqual(body["mode"], "local")
        self.assertTrue(any("not configured" in n for n in body["notices"]))

    def test_analyst_input_validation(self):
        self.assertEqual(self.post("/api/analyst/ask", {"question": ""})[0], 400)
        self.assertEqual(self.post("/api/analyst/ask", {"question": "x" * 501})[0], 400)
        self.assertEqual(self.post("/api/analyst/ask", {"question": "hi", "mode": "gpt"})[0], 400)
        self.assertEqual(self.post("/api/analyst/ask", {"question": "hi"}, "text/plain")[0], 415)

    def test_recommendation_question_never_invents_a_verdict(self):
        _, body = self.post("/api/analyst/ask", {"question": "Should we stop the referral programme?"})
        self.assertEqual(body["intent"], "recommend")
        self.assertIn("pending", " ".join(body["summary"]).lower())


class NumberGuardTests(unittest.TestCase):
    def test_accepts_rounded_source_numbers(self):
        ctx = {"value": -4.8512, "rate": 0.5479, "money": 501831.09}
        self.assertEqual(external.unverified_numbers("Revenue fell 4.85%, retention 54.8%, Q2 501,831", [ctx]), [])

    def test_flags_invented_numbers(self):
        self.assertEqual(external.unverified_numbers("Revenue fell 7.3%", [{"value": -4.85}]), ["7.3"])


if __name__ == "__main__":
    unittest.main()
