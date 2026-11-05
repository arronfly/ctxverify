"""End-to-end checks against the example packs."""

from __future__ import annotations

import unittest
from pathlib import Path

from ctxverify.checks import run_checks
from ctxverify.loader import load_pack

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def rules_fired(report) -> set[str]:
    return {finding.rule for finding in report.findings}


class CleanPackTests(unittest.TestCase):
    def test_clean_pack_has_no_findings(self) -> None:
        pack = load_pack(EXAMPLES / "clean-pack")
        report = run_checks(pack)
        self.assertEqual(report.findings, [], msg=report.to_text())
        self.assertEqual(report.exit_code(), 0)

    def test_clean_pack_stats(self) -> None:
        pack = load_pack(EXAMPLES / "clean-pack")
        report = run_checks(pack)
        self.assertEqual(report.stats["claims"], 2)
        self.assertEqual(report.stats["evidence"], 2)
        self.assertEqual(report.stats["sources"], 2)


class BrokenPackTests(unittest.TestCase):
    def setUp(self) -> None:
        pack = load_pack(EXAMPLES / "broken-pack")
        self.report = run_checks(pack)

    def test_every_planted_defect_is_caught(self) -> None:
        expected = {
            "provenance.missing",
            "provenance.dangling",
            "provenance.quote",
            "links.broken",
            "ids.duplicate",
            "ids.collision",
            "status.inconsistent",
            "contradiction.unresolved",
            "freshness.stale",
            "duplicate.claim",
            "orphan.source",
            "orphan.entity",
            "hygiene.secret",
            "hygiene.pii",
        }
        self.assertTrue(
            expected.issubset(rules_fired(self.report)),
            msg=f"missing rules: {expected - rules_fired(self.report)}",
        )

    def test_exit_code_is_one(self) -> None:
        self.assertEqual(self.report.exit_code(), 1)

    def test_strict_mode_also_fails(self) -> None:
        self.assertEqual(self.report.exit_code(strict=True), 1)

    def test_report_serialises(self) -> None:
        payload = self.report.to_dict()
        self.assertEqual(payload["status"], "fail")
        self.assertGreater(payload["counts"]["error"], 0)
        self.assertIn("findings", payload)

    def test_sarif_serialises(self) -> None:
        import json

        payload = json.loads(self.report.to_sarif())
        self.assertEqual(payload["version"], "2.1.0")
        self.assertTrue(payload["runs"][0]["results"])


class RuleSelectionTests(unittest.TestCase):
    def test_only_the_selected_rule_runs(self) -> None:
        pack = load_pack(EXAMPLES / "broken-pack")
        report = run_checks(pack, {"rules": {"identity"}})
        self.assertEqual(rules_fired(report), {"ids.duplicate", "ids.collision"})

    def test_excluding_a_rule(self) -> None:
        pack = load_pack(EXAMPLES / "broken-pack")
        report = run_checks(pack, {"exclude_rules": {"hygiene"}})
        self.assertNotIn("hygiene.secret", rules_fired(report))


class LoaderTests(unittest.TestCase):
    def test_missing_pack_raises(self) -> None:
        from ctxverify.loader import PackLoadError

        with self.assertRaises(PackLoadError):
            load_pack("/tmp/definitely-not-a-pack-ctxverify")

    def test_missing_files_are_reported(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report = run_checks(load_pack(tmp))
            self.assertIn("pack.structure", rules_fired(report))
            self.assertEqual(report.exit_code(), 1)

    def test_unparsable_json_is_reported(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "manifest.json").write_text("{not json", encoding="utf-8")
            report = run_checks(load_pack(tmp))
            self.assertIn("pack.structure", rules_fired(report))


if __name__ == "__main__":
    unittest.main()
