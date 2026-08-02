"""Retired-path write suppression (2026-08-01 cleanup pipeline).

The delete_candidate set from the 2026-07-30 disposition audit must never be
recreated by any generator. Suppression is enforced in generate.py's patched
Path.write_text, the choke point every generator write funnels through.
"""
import json
import sys
import unittest
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN_DIR))

import generate  # noqa: E402  (import installs the patched Path.write_text)


class TestRetiredSuppression(unittest.TestCase):
    def test_retired_set_loaded(self):
        self.assertGreater(len(generate.RETIRED_PATHS), 13000)

    def test_disjoint_from_redirect_map(self):
        redirect_map = json.loads(
            (GEN_DIR / "data" / "redirect_map.json").read_text(encoding="utf-8")
        )
        overlap = generate.RETIRED_PATHS & set(redirect_map)
        self.assertEqual(len(overlap), 0, f"stubs would be suppressed: {sorted(overlap)[:5]}")

    def test_write_to_retired_path_is_suppressed(self):
        rel = sorted(generate.RETIRED_PATHS)[0]
        target = generate._WEBSITE_ROOT / rel
        marker = "SUPPRESSION-TEST-MUST-NOT-LAND"
        result = target.write_text(marker, encoding="utf-8")
        self.assertEqual(result, 0)
        self.assertIn(rel, generate.SUPPRESSED_WRITES)
        if target.exists():
            self.assertNotIn(marker, target.read_text(encoding="utf-8"))

    def test_write_to_non_retired_path_still_works(self):
        tmp = generate._WEBSITE_ROOT / "_generator" / "tests" / "_tmp_write_check.txt"
        try:
            n = tmp.write_text("ok", encoding="utf-8")
            self.assertGreater(n, 0)
            self.assertEqual(tmp.read_text(encoding="utf-8"), "ok")
        finally:
            tmp.unlink(missing_ok=True)

    def test_paths_outside_website_root_unaffected(self):
        self.assertIsNone(generate._retired_rel(Path("C:/somewhere/else/x.html")))


if __name__ == "__main__":
    unittest.main()
