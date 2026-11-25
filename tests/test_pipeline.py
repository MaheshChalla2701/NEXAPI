import sqlite3
import tempfile
import unittest
from pathlib import Path

from pipeline import build_db, stats, validate


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "app.db"
        build_db.build("mock", cls.db, {})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_mock_build_validates(self):
        conn = sqlite3.connect(self.db)
        self.assertTrue(validate.run(conn))
        conn.close()

    def test_bridge_reconciles_exactly(self):
        conn = sqlite3.connect(self.db)
        total = conn.execute("SELECT value FROM kpi WHERE kpi_id = 'revenue_change_pct'").fetchone()[0]
        central = conn.execute("SELECT SUM(central_pp) FROM bridge_item").fetchone()[0]
        conn.close()
        self.assertAlmostEqual(central, total, places=6)

    def test_mock_is_labelled_and_has_no_recommendations(self):
        conn = sqlite3.connect(self.db)
        source = conn.execute("SELECT value FROM run_metadata WHERE key = 'data_source'").fetchone()[0]
        verdicts = {r[0] for r in conn.execute("SELECT recommendation FROM initiative")}
        conn.close()
        self.assertEqual(source, "mock")
        self.assertEqual(verdicts, {"PENDING"})

    def test_build_is_deterministic(self):
        other = Path(self.tmp.name) / "again.db"
        build_db.build("mock", other, {})
        q = "SELECT cause, central_pp, low_pp, high_pp FROM bridge_item ORDER BY position"
        a, b = sqlite3.connect(self.db), sqlite3.connect(other)
        self.assertEqual(a.execute(q).fetchall(), b.execute(q).fetchall())
        a.close(), b.close()

    def test_validation_rejects_unreconciled_bridge(self):
        broken = Path(self.tmp.name) / "broken.db"
        broken.write_bytes(self.db.read_bytes())
        conn = sqlite3.connect(broken)
        conn.execute("UPDATE bridge_item SET central_pp = central_pp + 1, high_pp = high_pp + 1 WHERE position = 1")
        with self.assertRaises(validate.ValidationError):
            validate.run(conn)
        conn.close()

    def test_failed_build_keeps_previous_database(self):
        before = self.db.read_bytes()
        with self.assertRaises(RuntimeError):
            build_db.build("assignment", self.db, {"data_root": Path(self.tmp.name)})
        self.assertEqual(self.db.read_bytes(), before)


class StatsTests(unittest.TestCase):
    def test_diff_in_proportions(self):
        r = stats.diff_in_proportions(60, 100, 50, 100)
        self.assertAlmostEqual(r["effect"], 0.10)
        self.assertLess(r["ci_low"], 0.10)
        self.assertGreater(r["ci_high"], 0.10)
        self.assertTrue(0 < r["p_value"] < 1)

    def test_srm_balanced_split_passes(self):
        self.assertGreater(stats.srm_two_arm(1000, 1000)["p_value"], 0.99)
        self.assertLess(stats.srm_two_arm(1000, 1200)["p_value"], 0.001)


if __name__ == "__main__":
    unittest.main()
