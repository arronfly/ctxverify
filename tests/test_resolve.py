"""Link resolution: Obsidian-style, not filesystem-style."""

from __future__ import annotations

import unittest

from ctxverify.resolve import LinkIndex, normalise_path, strip_wikilink


class ResolveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = LinkIndex(
            paths=[
                "wiki/concepts/C-001_Context_Packs.md",
                "wiki/concepts/C-002_Evidence.md",
                "vault/inbox/note.md",
                "notes/alias-holder.md",
            ],
            aliases={"MHA": "wiki/concepts/C-002_Evidence.md"},
        )

    def test_exact_path(self) -> None:
        self.assertEqual(
            self.index.resolve("wiki/concepts/C-001_Context_Packs.md"),
            "wiki/concepts/C-001_Context_Packs.md",
        )

    def test_path_without_extension(self) -> None:
        self.assertEqual(
            self.index.resolve("wiki/concepts/C-001_Context_Packs"),
            "wiki/concepts/C-001_Context_Packs.md",
        )

    def test_wikilink_syntax(self) -> None:
        self.assertEqual(
            self.index.resolve("[[C-002_Evidence]]"),
            "wiki/concepts/C-002_Evidence.md",
        )

    def test_wikilink_with_alias_and_heading(self) -> None:
        self.assertEqual(
            self.index.resolve("[[C-002_Evidence|see this]]"),
            "wiki/concepts/C-002_Evidence.md",
        )
        self.assertEqual(
            self.index.resolve("[[C-002_Evidence#Architecture]]"),
            "wiki/concepts/C-002_Evidence.md",
        )

    def test_partial_path_suffix(self) -> None:
        self.assertEqual(
            self.index.resolve("concepts/C-001_Context_Packs"),
            "wiki/concepts/C-001_Context_Packs.md",
        )

    def test_basename_across_folders(self) -> None:
        self.assertEqual(self.index.resolve("note"), "vault/inbox/note.md")

    def test_alias(self) -> None:
        self.assertEqual(self.index.resolve("MHA"), "wiki/concepts/C-002_Evidence.md")

    def test_unresolvable(self) -> None:
        self.assertIsNone(self.index.resolve("[[No Such Note]]"))

    def test_strip(self) -> None:
        self.assertEqual(strip_wikilink("[[a|b]]"), "a")
        self.assertEqual(strip_wikilink("a#b"), "a")

    def test_normalise(self) -> None:
        self.assertEqual(normalise_path("./a/b.md"), "a/b.md")
        self.assertEqual(normalise_path("a\\b.md"), "a/b.md")


if __name__ == "__main__":
    unittest.main()
