# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-05

### Added

- The 16 rules of the first release:
  - `pack.structure` — Pack files are present and parseable
  - `provenance.missing` — Claims are backed by evidence
  - `provenance.dangling` — Evidence points at things that exist
  - `provenance.quote` — Quotes are present and untampered
  - `links.broken` — Links resolve to real files
  - `ids.duplicate` — Identifiers are unique
  - `ids.collision` — Numbered files do not collide
  - `status.inconsistent` — Claim status matches its evidence
  - `contradiction.unresolved` — Contradictions are tracked and closed
  - `freshness.stale` — Claims are still fresh
  - `duplicate.claim` — The same fact is not stated twice
  - `orphan.source` — Sources are used
  - `orphan.entity` — Entities are used
  - `hygiene.secret` — No credentials in the pack
  - `hygiene.pii` — No personal contact details in the pack
  - `action.unverified` — Reported actions really happened
- CLI commands: `check`, `init`, `export obsidian`, `export llmwiki`,
  `verify-actions`, `rules`, and `mcp`.
- Output formats for `check`: text, JSON and SARIF; `verify-actions` emits
  text or JSON.
- Adapters for Obsidian vaults and llmwiki projects.
- An MCP server over stdio with four tools: `check_pack`, `list_claims`,
  `get_claim` and `verify_actions`.
- The action verifier, which checks an agent's reported actions against the
  filesystem.
- The exit code contract: `0` for a clean pack, `1` for blocking findings
  (including warnings and info under `--strict`), and `2` when the pack cannot
  be read or the invocation is unusable.

### Notes

0.1.0 is the first public release. The Context Pack Format version is 0.1.
