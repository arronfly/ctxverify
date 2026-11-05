"""The action verifier: does the filesystem agree with the report?"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ctxverify.checks.actions import load_actions, verify_actions


class ActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "notes").mkdir()
        (self.root / "notes" / "a.md").write_text("alpha", encoding="utf-8")
        (self.root / "notes" / "b.md").write_text("beta", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_true_claims_produce_no_findings(self) -> None:
        findings = verify_actions(
            [
                {"id": "a-1", "action": "archived", "path": "notes/a.md"},
                {"id": "a-2", "action": "deleted", "path": "notes/gone.md"},
            ],
            self.root,
        )
        self.assertEqual(findings, [])

    def test_false_archive_is_caught(self) -> None:
        findings = verify_actions(
            [{"id": "a-1", "action": "archived", "path": "notes/missing.md"}], self.root
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "action.unverified")
        self.assertIn("does not exist", findings[0].message)

    def test_count_must_match_the_list(self) -> None:
        findings = verify_actions(
            [
                {
                    "id": "a-1",
                    "action": "archived",
                    "paths": ["notes/a.md", "notes/b.md"],
                    "count": 8,
                }
            ],
            self.root,
        )
        self.assertTrue(any("claims 8 file(s) but lists 2" in f.message for f in findings))

    def test_move_requires_the_old_path_to_be_gone(self) -> None:
        findings = verify_actions(
            [{"id": "a-1", "action": "moved", "path": "notes/a.md", "from": "notes/b.md"}],
            self.root,
        )
        self.assertTrue(any("still exists" in f.message for f in findings))

    def test_hash_mismatch(self) -> None:
        findings = verify_actions(
            [{"id": "a-1", "action": "wrote", "path": "notes/a.md", "sha256": "0" * 64}],
            self.root,
        )
        self.assertTrue(any("content hash" in f.message for f in findings))

    def test_unknown_action(self) -> None:
        findings = verify_actions([{"id": "a-1", "action": "teleported", "path": "notes/a.md"}], self.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("unknown action", findings[0].message)

    def test_load_actions_skips_comments(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as handle:
            handle.write("# a comment\n")
            handle.write(json.dumps({"id": "a-1", "action": "exists", "path": "notes/a.md"}) + "\n")
            path = handle.name
        records = load_actions(path)
        self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
