"""Behaviour that was wrong in earlier drafts and is now fixed.

Each test here covers a behaviour a reader of the docs would otherwise have
no way to check.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ctxverify.checks import run_checks
from ctxverify.loader import load_pack
from ctxverify.model import Claim, Entity, Manifest, Pack, Source
from ctxverify.scaffold import scaffold_pack

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def write_pack(directory: Path, manifest: dict, claims: list[dict], **files: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "claims.jsonl").write_text(
        "".join(json.dumps(c) + "\n" for c in claims), encoding="utf-8"
    )
    (directory / "evidence.jsonl").write_text(files.get("evidence", ""), encoding="utf-8")
    (directory / "entities.json").write_text(
        files.get("entities", '{"entities": []}'), encoding="utf-8"
    )
    (directory / "relations.json").write_text(
        files.get("relations", '{"relations": []}'), encoding="utf-8"
    )
    (directory / "contradictions.json").write_text(
        files.get("contradictions", '{"contradictions": []}'), encoding="utf-8"
    )
    (directory / "freshness.json").write_text(
        files.get("freshness", '{"policy": {}, "claims": {}}'), encoding="utf-8"
    )
    (directory / "README.md").write_text(files.get("readme", "# pack\n"), encoding="utf-8")
    return directory


class RuleSelectionTests(unittest.TestCase):
    def test_full_rule_id_selects_exactly_that_rule(self) -> None:
        pack = load_pack(EXAMPLES / "broken-pack")
        report = run_checks(pack, {"rules": {"ids.duplicate"}})
        self.assertEqual({f.rule for f in report.findings}, {"ids.duplicate"})

    def test_group_name_still_selects_the_whole_group(self) -> None:
        pack = load_pack(EXAMPLES / "broken-pack")
        report = run_checks(pack, {"rules": {"provenance"}})
        self.assertEqual(
            {f.rule for f in report.findings},
            {"provenance.missing", "provenance.dangling", "provenance.quote"},
        )

    def test_excluding_a_single_rule(self) -> None:
        pack = load_pack(EXAMPLES / "broken-pack")
        report = run_checks(pack, {"exclude_rules": {"hygiene.secret"}})
        self.assertNotIn("hygiene.secret", {f.rule for f in report.findings})
        self.assertIn("hygiene.pii", {f.rule for f in report.findings})


class StructureTests(unittest.TestCase):
    def test_wrong_collection_shape_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_pack(
                Path(tmp) / "pack",
                {"format_version": "0.1", "pack_id": "p", "sources": []},
                [],
                entities='{"items": []}',
            )
            report = run_checks(load_pack(Path(tmp) / "pack"))
            structure = [f for f in report.findings if f.rule == "pack.structure"]
            self.assertTrue(structure)
            self.assertIn("entities", structure[0].message)

    def test_wrong_freshness_shape_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_pack(
                Path(tmp) / "pack",
                {"format_version": "0.1", "pack_id": "p", "sources": []},
                [],
                freshness="[]",
            )
            report = run_checks(load_pack(Path(tmp) / "pack"))
            self.assertTrue([f for f in report.findings if f.rule == "pack.structure"])

    def test_newer_minor_of_the_same_major_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_pack(
                Path(tmp) / "pack",
                {"format_version": "0.9", "pack_id": "p", "sources": []},
                [],
            )
            report = run_checks(load_pack(Path(tmp) / "pack"))
            messages = [f.message for f in report.findings]
            self.assertTrue(any("0.9" in m for m in messages))
            self.assertFalse(any(f.severity == "error" for f in report.findings))

    def test_different_major_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_pack(
                Path(tmp) / "pack",
                {"format_version": "1.0", "pack_id": "p", "sources": []},
                [],
            )
            report = run_checks(load_pack(Path(tmp) / "pack"))
            self.assertEqual(report.exit_code(), 1)
            self.assertTrue(
                any(f.rule == "pack.structure" and f.severity == "error" for f in report.findings)
            )


class EntityAndAliasTests(unittest.TestCase):
    def test_entity_name_does_not_resolve_a_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_pack(
                Path(tmp) / "pack",
                {"format_version": "0.1", "pack_id": "p", "sources": []},
                [
                    {
                        "id": "clm-001",
                        "text": "x",
                        "status": "asserted",
                        "links": [{"target": "[[Locator]]", "resolved": None}],
                    }
                ],
                entities='{"entities": [{"id": "ent-001", "name": "Locator"}]}',
            )
            report = run_checks(load_pack(Path(tmp) / "pack"))
            broken = [f for f in report.findings if f.rule == "links.broken"]
            self.assertEqual(len(broken), 1)
            self.assertIn("entity", broken[0].hint or "")

    def test_source_alias_resolves_a_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_pack(
                Path(tmp) / "pack",
                {
                    "format_version": "0.1",
                    "pack_id": "p",
                    "sources": [
                        {"id": "src-001", "path": "notes/a.md", "aliases": ["Short Name"]}
                    ],
                },
                [
                    {
                        "id": "clm-001",
                        "text": "x",
                        "status": "asserted",
                        "links": [{"target": "[[Short Name]]", "resolved": None}],
                    }
                ],
            )
            report = run_checks(load_pack(Path(tmp) / "pack"))
            self.assertFalse([f for f in report.findings if f.rule == "links.broken"])


class NamespaceTests(unittest.TestCase):
    def _pack_with_two_numbers(self, namespace_a=None, namespace_b=None) -> Pack:
        sources = [
            Source(id="src-001", path="a/C-001_One.md"),
            Source(id="src-002", path="b/C-001_Two.md"),
        ]
        if namespace_a:
            sources[0].extra["namespace"] = namespace_a
        if namespace_b:
            sources[1].extra["namespace"] = namespace_b
        return Pack(
            root=".",
            manifest=Manifest(pack_id="p", sources=sources),
            claims=[Claim(id="clm-001", text="x")],
        )

    def test_same_number_in_the_default_namespace_collides(self) -> None:
        report = run_checks(self._pack_with_two_numbers())
        self.assertTrue([f for f in report.findings if f.rule == "ids.collision"])

    def test_different_namespaces_do_not_collide(self) -> None:
        report = run_checks(self._pack_with_two_numbers(namespace_a="alpha", namespace_b="beta"))
        self.assertFalse([f for f in report.findings if f.rule == "ids.collision"])

    def test_hyphenated_document_names_are_not_card_numbers(self) -> None:
        pack = Pack(
            root=".",
            manifest=Manifest(
                pack_id="p",
                sources=[
                    Source(id="src-001", path="raw/acme-1077-pricing.md"),
                    Source(id="src-002", path="raw/acme-1077-synergy.md"),
                ],
            ),
        )
        report = run_checks(pack)
        self.assertFalse([f for f in report.findings if f.rule == "ids.collision"])


class UnknownKeyTests(unittest.TestCase):
    def test_unknown_keys_survive_a_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_pack(
                Path(tmp) / "pack",
                {"format_version": "0.1", "pack_id": "p", "sources": []},
                [],
                entities='{"entities": [{"id": "ent-001", "name": "X", "futureField": 42}]}',
            )
            pack = load_pack(Path(tmp) / "pack")
            self.assertEqual(pack.entities[0].extra.get("futureField"), 42)


class ReportTests(unittest.TestCase):
    def test_duration_is_reported(self) -> None:
        pack = load_pack(EXAMPLES / "clean-pack")
        report = run_checks(pack)
        self.assertIsInstance(report.duration_ms, int)

    def test_strict_is_carried_in_the_report(self) -> None:
        pack = load_pack(EXAMPLES / "clean-pack")
        report = run_checks(pack)
        report.strict = True
        self.assertIn("strict", report.to_dict())
        self.assertTrue(report.to_dict()["strict"])


class ScaffoldTests(unittest.TestCase):
    def test_scaffolded_pack_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = scaffold_pack(Path(tmp) / "pack")
            report = run_checks(pack)
            self.assertEqual(report.findings, [], msg=report.to_text())


if __name__ == "__main__":
    unittest.main()
