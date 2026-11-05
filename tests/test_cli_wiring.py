"""The CLI's wiring, tested end to end.

Every documented flag has a path through the command line. These tests
exercise that path, because a feature whose wiring could be deleted and
whose suite stayed green is not a feature.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ctxverify.cli import main

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class FlagWiringTests(unittest.TestCase):
    def test_no_path_defaults_to_the_current_directory(self) -> None:
        import os

        previous = os.getcwd()
        os.chdir(EXAMPLES / "clean-pack")
        try:
            code, output, _ = run_cli("check")
        finally:
            os.chdir(previous)
        self.assertEqual(code, 0)
        self.assertIn("PASS", output)

    def test_no_pii_skips_only_the_personal_detail_check(self) -> None:
        code, output, _ = run_cli("check", str(EXAMPLES / "broken-pack"), "--no-pii")
        self.assertEqual(code, 1)
        self.assertIn("hygiene.secret", output)
        self.assertNotIn("hygiene.pii", output)

    def test_scan_text_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            pack.mkdir()
            (pack / "manifest.json").write_text(
                json.dumps(
                    {
                        "format_version": "0.1",
                        "pack_id": "p",
                        "sources": [{"id": "src-001", "path": "a.md"}],
                    }
                ),
                encoding="utf-8",
            )
            (pack / "claims.jsonl").write_text(
                json.dumps(
                    {
                        "id": "clm-001",
                        "text": "see [[Nowhere]] for detail",
                        "status": "asserted",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            for name, body in (
                ("evidence.jsonl", ""),
                ("entities.json", '{"entities": []}'),
                ("relations.json", '{"relations": []}'),
                ("contradictions.json", '{"contradictions": []}'),
                ("freshness.json", '{"policy": {}, "claims": {}}'),
                ("README.md", "# p\n"),
            ):
                (pack / name).write_text(body, encoding="utf-8")

            code, output, _ = run_cli("check", str(pack))
            self.assertEqual(code, 0, msg=output)

            code, output, _ = run_cli("check", str(pack), "--scan-text-links")
            self.assertEqual(code, 1)
            self.assertIn("links.broken", output)

    def test_actions_inside_check(self) -> None:
        code, output, _ = run_cli(
            "check",
            str(EXAMPLES / "clean-pack"),
            "--actions",
            str(EXAMPLES / "actions.jsonl"),
            "--actions-root",
            str(EXAMPLES / "obsidian-vault"),
        )
        self.assertEqual(code, 1)
        self.assertIn("action.unverified", output)

    def test_color_does_not_change_the_verdict(self) -> None:
        code, output, _ = run_cli("check", str(EXAMPLES / "clean-pack"), "--color")
        self.assertEqual(code, 0)
        self.assertIn("PASS", output)

    def test_a_pack_that_cannot_be_opened_exits_two(self) -> None:
        code, _, err = run_cli("check", "/tmp/definitely-not-a-pack-ctxverify")
        self.assertEqual(code, 2)
        self.assertIn("ctxverify:", err)

    def test_rule_selection_through_the_cli(self) -> None:
        code, output, _ = run_cli(
            "check", str(EXAMPLES / "broken-pack"), "--rule", "provenance.missing"
        )
        self.assertEqual(code, 1)
        self.assertIn("provenance.missing", output)
        self.assertNotIn("ids.duplicate", output)

    def test_exclude_rule_through_the_cli(self) -> None:
        code, output, _ = run_cli(
            "check", str(EXAMPLES / "broken-pack"), "--exclude-rule", "hygiene"
        )
        self.assertNotIn("hygiene.", output)
        self.assertEqual(code, 1)


class ExportWiringTests(unittest.TestCase):
    def test_export_markdown_through_the_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pack"
            code, output, _ = run_cli(
                "export", "markdown", str(EXAMPLES / "obsidian-vault"), "--out", str(out)
            )
            self.assertEqual(code, 0, msg=output)
            self.assertTrue((out / "claims.jsonl").exists())
            code, output, _ = run_cli("check", str(out))
            self.assertEqual(code, 1)
            self.assertIn("links.broken", output)


class McpToolTests(unittest.TestCase):
    def setUp(self) -> None:
        from ctxverify.mcp.server import call_tool

        self.call_tool = call_tool

    def test_list_claims(self) -> None:
        payload = self.call_tool("list_claims", {"path": str(EXAMPLES / "clean-pack")}, None)
        self.assertEqual(payload["total"], 2)
        self.assertEqual(len(payload["claims"]), 2)

    def test_list_claims_filters(self) -> None:
        payload = self.call_tool(
            "list_claims", {"path": str(EXAMPLES / "clean-pack"), "status": "verified"}, None
        )
        self.assertTrue(payload["claims"])

        payload = self.call_tool(
            "list_claims", {"path": str(EXAMPLES / "clean-pack"), "status": "refuted"}, None
        )
        self.assertEqual(payload["claims"], [])

    def test_get_claim(self) -> None:
        payload = self.call_tool(
            "get_claim", {"path": str(EXAMPLES / "clean-pack"), "claim_id": "clm-001"}, None
        )
        self.assertEqual(payload["claim"]["id"], "clm-001")
        self.assertTrue(payload["evidence"])

    def test_verify_actions(self) -> None:
        payload = self.call_tool(
            "verify_actions",
            {
                "actions": [{"id": "a-1", "action": "archived", "path": "notes/nope.md"}],
                "root": str(EXAMPLES / "obsidian-vault"),
            },
            None,
        )
        self.assertFalse(payload["verified"])
        self.assertTrue(payload["findings"])


class RulesOutputTests(unittest.TestCase):
    def test_rules_lists_every_rule_and_its_group(self) -> None:
        from ctxverify.rules import RULES

        code, output, _ = run_cli("rules")
        self.assertEqual(code, 0)
        for rule in RULES:
            self.assertIn(rule.id, output)


if __name__ == "__main__":
    unittest.main()
