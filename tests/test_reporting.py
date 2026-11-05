"""The report must never disagree with itself.

A linter that prints PASS and exits 1 is worse than one that prints nothing:
the reader believes the output. These tests pin the places where the three
representations — the text header, the JSON payload and the exit code — could
drift apart.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ctxverify.checks import run_checks
from ctxverify.cli import main
from ctxverify.loader import load_pack
from ctxverify.mcp.server import call_tool

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def run_cli(*argv: str) -> tuple[int, str]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(list(argv))
    return code, buffer.getvalue()


class FilterDoesNotChangeTheVerdictTests(unittest.TestCase):
    """`--min-severity` filters what is printed, not what is true."""

    def setUp(self) -> None:
        self.broken = str(EXAMPLES / "broken-pack")

    def test_exit_code_ignores_the_filter(self) -> None:
        code_all, _ = run_cli("check", self.broken)
        code_errors, _ = run_cli("check", self.broken, "--min-severity", "error")
        self.assertEqual(code_all, 1)
        self.assertEqual(code_errors, 1)

    def test_text_header_counts_the_whole_pack(self) -> None:
        code, output = run_cli("check", self.broken, "--min-severity", "error")
        self.assertEqual(code, 1)
        # The header always describes every finding, not just the listed ones.
        self.assertIn("13 error(s), 8 warning(s), 2 info", output)
        # …while only errors are listed.
        self.assertIn("ERROR", output)
        self.assertNotIn("orphan.source", output)

    def test_json_reports_both_the_shown_and_the_total(self) -> None:
        code, output = run_cli("check", self.broken, "--min-severity", "error", "--format", "json")
        payload = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(payload["total_findings"], 23)
        self.assertLess(payload["reported"], payload["total_findings"])
        self.assertEqual(payload["total_counts"]["warning"], 8)
        self.assertEqual(payload["counts"]["warning"], 0)
        self.assertTrue(all(f["severity"] == "error" for f in payload["findings"]))

    def test_strict_is_reflected_in_the_header_and_the_payload(self) -> None:
        code, output = run_cli("check", str(EXAMPLES / "clean-pack"), "--strict")
        self.assertEqual(code, 0)

        # A pack with only warnings: strict must fail and say so.
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            pack.mkdir()
            (pack / "manifest.json").write_text(
                json.dumps({"format_version": "0.1", "pack_id": "p", "sources": []}), encoding="utf-8"
            )
            (pack / "claims.jsonl").write_text(
                json.dumps(
                    {
                        "id": "clm-001",
                        "text": "an old claim",
                        "status": "asserted",
                        "updated_at": "2020-01-01",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (pack / "evidence.jsonl").write_text("", encoding="utf-8")
            (pack / "entities.json").write_text('{"entities": []}', encoding="utf-8")
            (pack / "relations.json").write_text('{"relations": []}', encoding="utf-8")
            (pack / "contradictions.json").write_text('{"contradictions": []}', encoding="utf-8")
            (pack / "freshness.json").write_text(
                json.dumps({"policy": {"default_ttl_days": 1}, "claims": {}}), encoding="utf-8"
            )
            (pack / "README.md").write_text("# p\n", encoding="utf-8")

            code, output = run_cli("check", str(pack))
            self.assertEqual(code, 0)
            self.assertIn("PASS", output)

            code, output = run_cli("check", str(pack), "--strict")
            self.assertEqual(code, 1)
            self.assertIn("FAIL", output)

            code, output = run_cli("check", str(pack), "--strict", "--format", "json")
            payload = json.loads(output)
            self.assertTrue(payload["strict"])
            self.assertEqual(payload["status"], "fail")


class McpParityTests(unittest.TestCase):
    """The MCP server must agree with the CLI."""

    def setUp(self) -> None:
        self.broken = str(EXAMPLES / "broken-pack")

    def test_verdict_matches_the_exit_code(self) -> None:
        payload = call_tool("check_pack", {"path": self.broken}, None)
        self.assertEqual(payload["verdict"], "fail")
        self.assertEqual(payload["total_findings"], 23)

    def test_min_severity_does_not_change_the_verdict(self) -> None:
        payload = call_tool(
            "check_pack", {"path": self.broken, "min_severity": "error"}, None
        )
        self.assertEqual(payload["verdict"], "fail")
        self.assertLess(payload["reported"], payload["total_findings"])
        self.assertEqual(payload["total_counts"]["warning"], 8)

    def test_strict_is_honoured(self) -> None:
        payload = call_tool("check_pack", {"path": self.broken, "strict": True}, None)
        self.assertTrue(payload["strict"])
        self.assertEqual(payload["status"], "fail")

    def test_rule_selection_narrows_the_findings(self) -> None:
        payload = call_tool(
            "check_pack", {"path": self.broken, "exclude_rules": ["hygiene.secret"]}, None
        )
        rules = {f["rule"] for f in payload["findings"]}
        self.assertNotIn("hygiene.secret", rules)
        self.assertIn("hygiene.pii", rules)


class NoDuplicateFindingsTests(unittest.TestCase):
    """One defect, one finding."""

    def test_unsupported_version_produces_one_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            pack.mkdir()
            (pack / "manifest.json").write_text(
                json.dumps({"format_version": "9.0", "pack_id": "p", "sources": []}), encoding="utf-8"
            )
            (pack / "claims.jsonl").write_text("", encoding="utf-8")
            (pack / "evidence.jsonl").write_text("", encoding="utf-8")
            (pack / "entities.json").write_text('{"entities": []}', encoding="utf-8")
            (pack / "relations.json").write_text('{"relations": []}', encoding="utf-8")
            (pack / "contradictions.json").write_text('{"contradictions": []}', encoding="utf-8")
            (pack / "freshness.json").write_text('{"policy": {}, "claims": {}}', encoding="utf-8")
            (pack / "README.md").write_text("# p\n", encoding="utf-8")

            report = run_checks(load_pack(pack))
            messages = [f.message for f in report.findings]
            self.assertEqual(len(messages), len(set(messages)), msg=messages)

    def test_bad_jsonl_line_produces_one_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            pack.mkdir()
            (pack / "manifest.json").write_text(
                json.dumps({"format_version": "0.1", "pack_id": "p", "sources": []}), encoding="utf-8"
            )
            (pack / "claims.jsonl").write_text("{not json}\n", encoding="utf-8")
            (pack / "evidence.jsonl").write_text("", encoding="utf-8")
            (pack / "entities.json").write_text('{"entities": []}', encoding="utf-8")
            (pack / "relations.json").write_text('{"relations": []}', encoding="utf-8")
            (pack / "contradictions.json").write_text('{"contradictions": []}', encoding="utf-8")
            (pack / "freshness.json").write_text('{"policy": {}, "claims": {}}', encoding="utf-8")
            (pack / "README.md").write_text("# p\n", encoding="utf-8")

            report = run_checks(load_pack(pack))
            messages = [f.message for f in report.findings]
            self.assertEqual(len(messages), len(set(messages)), msg=messages)


if __name__ == "__main__":
    unittest.main()
