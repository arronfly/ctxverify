"""Regression tests for the findings of the pre-release review.

Each test here corresponds to a specific defect that a reviewer found and
that would otherwise have shipped.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ctxverify.checks import run_checks
from ctxverify.checks.actions import load_actions, verify_actions
from ctxverify.cli import main
from ctxverify.loader import load_pack
from ctxverify.mcp.server import call_tool

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def build_pack(
    directory: Path,
    manifest: dict | None = None,
    claims: list[dict] | None = None,
    evidence: list[dict] | None = None,
    entities: dict | None = None,
    relations: dict | None = None,
    contradictions: dict | None = None,
    freshness: dict | None = None,
    readme: str = "# pack\n",
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    if manifest is None:
        manifest = {
            "format_version": "0.1",
            "pack_id": "p",
            "sources": [{"id": "src-001", "path": "notes/a.md"}],
        }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "claims.jsonl").write_text(
        "".join(json.dumps(c) + "\n" for c in (claims or [])), encoding="utf-8"
    )
    (directory / "evidence.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in (evidence or [])), encoding="utf-8"
    )
    (directory / "entities.json").write_text(
        json.dumps(entities if entities is not None else {"entities": []}), encoding="utf-8"
    )
    (directory / "relations.json").write_text(
        json.dumps(relations if relations is not None else {"relations": []}), encoding="utf-8"
    )
    (directory / "contradictions.json").write_text(
        json.dumps(contradictions if contradictions is not None else {"contradictions": []}),
        encoding="utf-8",
    )
    (directory / "freshness.json").write_text(
        json.dumps(freshness if freshness is not None else {"policy": {}, "claims": {}}),
        encoding="utf-8",
    )
    (directory / "README.md").write_text(readme, encoding="utf-8")
    return directory


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class EvidenceMustNameSomethingTests(unittest.TestCase):
    """C1: a verified claim whose evidence names no claim and no source."""

    def test_empty_claim_id_is_a_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack",
                claims=[
                    {
                        "id": "clm-001",
                        "text": "Trustworthy.",
                        "status": "verified",
                        "evidence": ["ev-001"],
                    }
                ],
                evidence=[
                    {
                        "id": "ev-001",
                        "claim_id": "",
                        "source_id": "",
                        "quote": "Trustworthy.",
                    }
                ],
            )
            report = run_checks(load_pack(pack))
            dangling = [f for f in report.findings if f.rule == "provenance.dangling"]
            self.assertEqual(len(dangling), 2, msg=report.to_text())
            self.assertEqual(report.exit_code(), 1)


class WrongTypedFieldsTests(unittest.TestCase):
    """C2 and m1: valid JSON of the wrong shape must not crash the run."""

    def _cases(self) -> list[tuple[str, dict]]:
        base = {
            "format_version": "0.1",
            "pack_id": "p",
            "sources": [{"id": "src-001", "path": "notes/a.md"}],
        }
        return [
            ("sources is a string", {**base, "sources": "nope"}),
            ("sources holds a number", {**base, "sources": [123]}),
            ("generator is a string", {**base, "generator": "foo"}),
            ("stats is a string", {**base, "stats": "abc"}),
            ("verification is a string", {**base, "verification": "zt"}),
        ]

    def test_manifest_fields_of_the_wrong_type_do_not_crash(self) -> None:
        for label, manifest in self._cases():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                pack = build_pack(Path(tmp) / "pack", manifest=manifest)
                report = run_checks(load_pack(pack))
                self.assertNotIn(
                    "ctxverify.internal",
                    {f.rule for f in report.findings},
                    msg=f"{label}: {report.to_text()}",
                )
                self.assertEqual(report.exit_code(), 1, msg=label)

    def test_evidence_locator_of_the_wrong_type_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack",
                evidence=[{"id": "ev-001", "claim_id": "c", "source_id": "s", "locator": "x"}],
            )
            report = run_checks(load_pack(pack))
            self.assertNotIn("ctxverify.internal", {f.rule for f in report.findings})
            self.assertEqual(report.exit_code(), 1)

    def test_a_string_where_a_list_belongs_is_one_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack",
                claims=[
                    {
                        "id": "clm-001",
                        "text": "x",
                        "status": "asserted",
                        "evidence": "ev-001",
                    }
                ],
            )
            report = run_checks(load_pack(pack))
            # The type error is reported once, naming the field.
            structure = [f for f in report.findings if f.rule == "pack.structure"]
            self.assertEqual(len(structure), 1, msg=report.to_text())
            self.assertIn("evidence must be an array", structure[0].message)
            # The string is read as one id, not as four characters.
            dangling = [f for f in report.findings if f.rule == "provenance.dangling"]
            self.assertEqual(len(dangling), 1, msg=report.to_text())
            self.assertIn("ev-001", dangling[0].message)


class RuleSelectionTests(unittest.TestCase):
    """M1: a misspelt rule must not silently turn a failing pack into PASS."""

    def test_unknown_rule_is_a_usage_error(self) -> None:
        code, _, err = run_cli("check", str(EXAMPLES / "broken-pack"), "--rule", "provanance")
        self.assertEqual(code, 2)
        self.assertIn("unknown rule", err)

    def test_unknown_exclude_rule_is_a_usage_error(self) -> None:
        code, _, err = run_cli(
            "check", str(EXAMPLES / "broken-pack"), "--exclude-rule", "provenance.missin"
        )
        self.assertEqual(code, 2)
        self.assertIn("unknown rule", err)


class LocationTests(unittest.TestCase):
    """M2: a finding's location must name a file that exists."""

    def test_duplicate_entity_id_points_at_entities_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack",
                entities={"entities": [{"id": "ent-001", "name": "A"}, {"id": "ent-001", "name": "B"}]},
            )
            report = run_checks(load_pack(pack))
            duplicates = [f for f in report.findings if f.rule == "ids.duplicate"]
            self.assertTrue(duplicates)
            for finding in duplicates:
                self.assertTrue(
                    finding.location.startswith("entities.json"),
                    msg=finding.location,
                )

    def test_duplicate_source_id_points_at_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack",
                manifest={
                    "format_version": "0.1",
                    "pack_id": "p",
                    "sources": [
                        {"id": "src-001", "path": "a.md"},
                        {"id": "src-001", "path": "b.md"},
                    ],
                },
            )
            report = run_checks(load_pack(pack))
            duplicates = [f for f in report.findings if f.rule == "ids.duplicate"]
            self.assertTrue(duplicates)
            for finding in duplicates:
                self.assertTrue(finding.location.startswith("manifest.json"), msg=finding.location)


class RelationTypeTests(unittest.TestCase):
    """M3: a relation must name its type."""

    def test_typeless_relation_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack",
                entities={"entities": [{"id": "ent-001", "name": "A"}, {"id": "ent-002", "name": "B"}]},
                relations={"relations": [{"id": "rel-001", "from": "ent-001", "to": "ent-002"}]},
            )
            report = run_checks(load_pack(pack))
            messages = [f.message for f in report.findings if f.rule == "status.inconsistent"]
            self.assertTrue(any("has no type" in m for m in messages), msg=report.to_text())


class HygieneCoverageTests(unittest.TestCase):
    """M4: a credential in any string of the pack must be found."""

    def test_token_in_a_source_title(self) -> None:
        token = "ghp_" + "A" * 36
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack",
                manifest={
                    "format_version": "0.1",
                    "pack_id": "p",
                    "sources": [{"id": "src-001", "path": "a.md", "title": f"deploy {token}"}],
                },
            )
            report = run_checks(load_pack(pack))
            self.assertIn("hygiene.secret", {f.rule for f in report.findings})

    def test_token_in_entity_properties(self) -> None:
        token = "ghp_" + "B" * 36
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack",
                entities={
                    "entities": [
                        {"id": "ent-001", "name": "A", "properties": {"token": token}}
                    ]
                },
            )
            report = run_checks(load_pack(pack))
            self.assertIn("hygiene.secret", {f.rule for f in report.findings})


class ActionSafetyTests(unittest.TestCase):
    """M5, M6, M7 and m9: the verifier must not be lied to, nor used as an oracle."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "notes").mkdir()
        (self.root / "notes" / "a.md").write_text("alpha", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_path_escaping_the_root_is_rejected(self) -> None:
        findings = verify_actions(
            [{"id": "a-1", "action": "exists", "path": "../../../../../../etc/hosts"}],
            self.root,
        )
        self.assertTrue(any("outside the root" in f.message for f in findings))

    def test_absolute_path_is_rejected(self) -> None:
        findings = verify_actions(
            [{"id": "a-1", "action": "wrote", "path": "/etc/hosts", "sha256": "0" * 64}],
            self.root,
        )
        self.assertTrue(any("outside the root" in f.message for f in findings))
        self.assertFalse(any("content hash" in f.message for f in findings))

    def test_a_non_object_line_is_an_error_not_a_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "actions.jsonl"
            path.write_text(
                json.dumps({"id": "a-1", "action": "exists", "path": "notes/a.md"}) + "\n"
                + json.dumps(["archived", "x.md"]) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_actions(path)

    def test_a_count_that_is_not_a_number(self) -> None:
        findings = verify_actions(
            [
                {
                    "id": "a-1",
                    "action": "archived",
                    "paths": ["notes/a.md", "notes/b.md"],
                    "count": "two",
                }
            ],
            self.root,
        )
        self.assertTrue(any("not a number" in f.message for f in findings))

    def test_a_paths_value_that_is_not_a_list(self) -> None:
        findings = verify_actions(
            [{"id": "a-1", "action": "archived", "paths": "notes/a.md"}],
            self.root,
        )
        self.assertTrue(any("not a list" in f.message for f in findings))

    def test_a_move_with_no_origin(self) -> None:
        findings = verify_actions(
            [{"id": "a-1", "action": "moved", "path": "notes/a.md"}],
            self.root,
        )
        self.assertTrue(any("names no 'from' path" in f.message for f in findings))


class CliErrorTests(unittest.TestCase):
    """M8: user errors produce messages, not tracebacks."""

    def test_export_a_missing_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli(
                "export", "obsidian", str(Path(tmp) / "typo"), "--out", str(Path(tmp) / "out")
            )
            self.assertEqual(code, 2)
            self.assertIn("ctxverify:", err)

    def test_init_over_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "afile"
            path.write_text("x", encoding="utf-8")
            code, _, err = run_cli("init", str(path))
            self.assertEqual(code, 2)
            self.assertIn("not a directory", err)


class FormatVersionTests(unittest.TestCase):
    """m12: a version is MAJOR.MINOR or it is not a version."""

    def test_a_version_that_is_not_major_minor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack", manifest={"format_version": "0", "pack_id": "p", "sources": []}
            )
            report = run_checks(load_pack(pack))
            self.assertTrue(
                any("MAJOR.MINOR" in f.message for f in report.findings), msg=report.to_text()
            )

    def test_a_three_part_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack",
                manifest={"format_version": "0.1.5", "pack_id": "p", "sources": []},
            )
            report = run_checks(load_pack(pack))
            self.assertTrue(
                any("MAJOR.MINOR" in f.message for f in report.findings), msg=report.to_text()
            )


class RequiredManifestFieldTests(unittest.TestCase):
    """m13: the manifest's required fields are required."""

    def test_missing_pack_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack", manifest={"format_version": "0.1", "sources": []}
            )
            report = run_checks(load_pack(pack))
            self.assertTrue(
                any("pack_id" in f.message for f in report.findings), msg=report.to_text()
            )


class McpTests(unittest.TestCase):
    """m16: a missing claim is an error, not an empty success."""

    def test_get_claim_raises_for_a_missing_claim(self) -> None:
        with self.assertRaises(KeyError):
            call_tool("get_claim", {"path": str(EXAMPLES / "clean-pack"), "claim_id": "nope"}, None)

    def test_list_claims_limit_zero(self) -> None:
        payload = call_tool(
            "list_claims", {"path": str(EXAMPLES / "clean-pack"), "limit": 0}, None
        )
        self.assertEqual(payload["claims"], [])


class InternalErrorTests(unittest.TestCase):
    """m14: a crash in ctxverify is its own rule, never the pack's fault."""

    def test_internal_errors_have_their_own_rule(self) -> None:
        from ctxverify.rules import RULES_BY_ID

        self.assertIn("ctxverify.internal", RULES_BY_ID)
        self.assertEqual(RULES_BY_ID["ctxverify.internal"].severity, "error")


class FrontmatterTests(unittest.TestCase):
    """m5: a nested map ends where the next top-level key begins."""

    def test_nested_maps_do_not_bleed(self) -> None:
        from ctxverify.frontmatter import parse_frontmatter

        raw = "---\nmeta:\n  author: someone\nother:\n  x: 1\n---\n"
        data = parse_frontmatter(raw)
        self.assertEqual(data["meta"], {"author": "someone"})
        self.assertEqual(data["other"], {"x": 1})


class StructureSurvivesNarrowingTests(unittest.TestCase):
    """m7: a structural error is reported whatever the run is narrowed to."""

    def test_a_broken_policy_is_reported_under_a_narrowed_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack",
                claims=[{"id": "clm-001", "text": "x", "status": "asserted"}],
                freshness={"policy": {"default_ttl_days": -5}, "claims": {}},
            )
            report = run_checks(load_pack(pack), {"rules": {"provenance"}})
            self.assertTrue(
                any(f.rule == "pack.structure" for f in report.findings), msg=report.to_text()
            )
            self.assertEqual(report.exit_code(), 1)


class LinkCaseTests(unittest.TestCase):
    """m2: the resolved path is compared the way the resolver compares it."""

    def test_a_resolved_path_that_differs_in_case_is_not_broken(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = build_pack(
                Path(tmp) / "pack",
                manifest={
                    "format_version": "0.1",
                    "pack_id": "p",
                    "sources": [{"id": "src-001", "path": "notes/a.md"}],
                },
                claims=[
                    {
                        "id": "clm-001",
                        "text": "x",
                        "status": "asserted",
                        "links": [{"target": "[[A]]", "resolved": "Notes/A.MD"}],
                    }
                ],
            )
            report = run_checks(load_pack(pack))
            self.assertFalse([f for f in report.findings if f.rule == "links.broken"])


if __name__ == "__main__":
    unittest.main()
