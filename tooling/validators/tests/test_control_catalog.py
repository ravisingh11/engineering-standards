from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class ControlCatalogPolicyTests(unittest.TestCase):
    def test_every_control_defaults_to_advisory_and_non_blocking(self) -> None:
        catalog = json.loads(
            (ROOT / "policies" / "control-catalog.yaml").read_text(encoding="utf-8")
        )

        for control in catalog["controls"]:
            with self.subTest(control_id=control["id"]):
                self.assertEqual(control["requiredness"], "advisory")
                self.assertFalse(control["blocking"])

    def test_distributed_catalogs_match_canonical_default_modes(self) -> None:
        canonical = json.loads(
            (ROOT / "policies" / "control-catalog.yaml").read_text(encoding="utf-8")
        )
        expected = {
            control["id"]: (control["requiredness"], control["blocking"])
            for control in canonical["controls"]
        }

        for relative_path in (
            ".guardrails/control-catalog.yaml",
            "examples/python-demo/.ai/control-catalog.yaml",
        ):
            with self.subTest(path=relative_path):
                distributed = json.loads(
                    (ROOT / relative_path).read_text(encoding="utf-8")
                )
                actual = {
                    control["id"]: (control["requiredness"], control["blocking"])
                    for control in distributed["controls"]
                }
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
