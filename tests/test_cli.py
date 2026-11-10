"""CLI behaviour and the MCP server."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ctxverify.cli import main

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def run_cli(*argv: str) -> tuple[int, str]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(list(argv))
    return code, buffer.getvalue()


class CliTests(unittest.TestCase):
    def test_check_clean_pack_exits_zero(self) -> None:
        code, output = run_cli("check", str(EXAMPLES / "clean-pack"))
        self.assertEqual(code, 0)
        self.assertIn("PASS", output)

    def test_check_broken_pack_exits_one(self) -> None:
        code, output = run_cli("check", str(EXAMPLES / "broken-pack"))
        self.assertEqual(code, 1)
        self.assertIn("FAIL", output)

    def test_json_output_parses(self) -> None:
        code, output = run_cli("check", str(EXAMPLES / "broken-pack"), "--format", "json")
        payload = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "fail")
        self.assertIn("findings", payload)

    def test_sarif_output_parses(self) -> None:
        code, output = run_cli("check", str(EXAMPLES / "broken-pack"), "--format", "sarif")
        payload = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(payload["version"], "2.1.0")

    def test_min_severity_filters_output(self) -> None:
        code, output = run_cli(
            "check", str(EXAMPLES / "broken-pack"), "--format", "json", "--min-severity", "error"
        )
        payload = json.loads(output)
        self.assertTrue(all(f["severity"] == "error" for f in payload["findings"]))
        self.assertEqual(len(payload["findings"]), 13)
        self.assertIn("provenance.missing", {f["rule"] for f in payload["findings"]})

    def test_quiet_prints_nothing(self) -> None:
        code, output = run_cli("check", str(EXAMPLES / "clean-pack"), "--quiet")
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "")

    def test_init_scaffolds_a_passing_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            code, _ = run_cli("init", str(target))
            self.assertEqual(code, 0)
            code, output = run_cli("check", str(target))
            self.assertEqual(code, 0, msg=output)

    def test_init_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            run_cli("init", str(target))
            code, _ = run_cli("init", str(target))
            self.assertEqual(code, 2)

    def test_export_obsidian_then_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            code, _ = run_cli("export", "obsidian", str(EXAMPLES / "obsidian-vault"), "--out", str(target))
            self.assertEqual(code, 0)
            code, output = run_cli("check", str(target))
            # The sample vault contains one deliberately broken wikilink.
            self.assertEqual(code, 1)
            self.assertIn("links.broken", output)

    def test_rules_lists_the_catalogue(self) -> None:
        code, output = run_cli("rules")
        self.assertEqual(code, 0)
        self.assertIn("provenance.missing", output)
        self.assertIn("action.unverified", output)

    def test_verify_actions_command(self) -> None:
        code, output = run_cli(
            "verify-actions", str(EXAMPLES / "actions.jsonl"), "--root", str(EXAMPLES / "obsidian-vault")
        )
        self.assertEqual(code, 1)
        self.assertIn("action.unverified", output)


class McpTests(unittest.TestCase):
    def setUp(self) -> None:
        from ctxverify.mcp.server import handle

        self.handle = handle

    def test_initialize(self) -> None:
        response = self.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, None)
        self.assertEqual(response["id"], 1)
        self.assertIn("protocolVersion", response["result"])

    def test_tools_list(self) -> None:
        response = self.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, None)
        names = [tool["name"] for tool in response["result"]["tools"]]
        self.assertIn("check_pack", names)
        self.assertIn("verify_actions", names)

    def test_every_tool_declares_the_four_annotations(self) -> None:
        response = self.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}, None)
        hints = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")
        for tool in response["result"]["tools"]:
            annotations = tool.get("annotations")
            self.assertIsNotNone(annotations, f"{tool['name']} declares no annotations")
            for hint in hints:
                self.assertIn(hint, annotations, f"{tool['name']} is missing {hint}")
                self.assertIsInstance(annotations[hint], bool, f"{tool['name']}.{hint} is not a boolean")
            self.assertTrue(annotations["readOnlyHint"], f"{tool['name']} claims to write")
            self.assertFalse(annotations["destructiveHint"], f"{tool['name']} claims to be destructive")
            self.assertFalse(annotations["openWorldHint"], f"{tool['name']} claims to touch the outside world")

    def test_tools_call_check_pack(self) -> None:
        response = self.handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "check_pack",
                    "arguments": {"path": str(EXAMPLES / "broken-pack")},
                },
            },
            None,
        )
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["verdict"], "fail")

    def test_notification_is_ignored(self) -> None:
        self.assertIsNone(self.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, None))


if __name__ == "__main__":
    unittest.main()
