# Security Policy

## What ctxverify does with your data

ctxverify reads files and reports on them. It does not send anything
anywhere, it does not call a network service, and it has no runtime
dependencies beyond the Python standard library.

`ctxv check` reads the pack directory and nothing else. `ctxv export` reads a
source corpus and writes a pack. `ctxv verify-actions` reads the filesystem
under the root you give it. `ctxv mcp` serves tools over stdio to the agent
that started it.

## Reporting a vulnerability

If you find a way to make ctxverify execute code, read a file outside the
directory it was pointed at, or leak data between packs, open a security
advisory on the repository rather than a public issue.

Include the version (`ctxv --version`), the smallest reproduction you can
manage, and what an attacker would gain.

## A note on packs themselves

A context pack is designed to travel between tools and between people. Two
things follow from that, and ctxverify checks both:

- **Credentials.** The `hygiene.secret` rule reports strings that look like
  API keys, tokens, private keys or JWTs. If one of them is real, rotate it —
  the report only tells you it is there, not that it was ever published.
- **Personal contact details.** The `hygiene.pii` rule reports email
  addresses, phone numbers and national id numbers. It is a warning, not an
  error: contact details are sometimes the point of a pack.

Both checks run on the pack's text: claim text and notes, evidence quotes,
entity names, relation notes, contradiction descriptions, and the pack's
README. `--no-pii` skips the personal-detail check; the credential check
always runs.
