# Context Pack Format (CPF) — version 0.1

**Status:** stable for 0.1
**License:** CC-BY-4.0 (this document). Implementations may be licensed under any terms.
**Reference implementation:** [ctxverify](https://github.com/arronfly/ctxverify)

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be interpreted
as described in RFC 2119.

---

## 0. Why this format exists

A knowledge compiler takes raw material and produces a wiki. The artifact it
produces is usually a pile of markdown, and the question "can I trust this?"
is answered by reading it — which is exactly the question an agent cannot
answer cheaply, and exactly the question a human stops asking after the
twentieth page.

This format makes the artifact **claim-shaped** rather than page-shaped, and
therefore **checkable** rather than merely readable. Every statement in a pack
is an atomic claim with a declared epistemic status; every claim points at
evidence; every evidence record points at a place in a source. A reader — a
human or an agent — can then ask the compiler's output questions that have
answers.

The format does two things and refuses to do a third:

- It records **what is claimed, what supports it, and how fresh it is**.
- It makes those records **portable** between compilers, tools and vendors.
- It does **not** prescribe how a pack is produced. Compilation is the
  compiler's business; judgement is the checker's.

## 1. Design rules

1. **A pack is a directory of plain text files.** No database, no binary
   blobs, no proprietary container. It must be readable with `cat`.
2. **Every file is independently parseable.** JSON for structured documents,
   JSON Lines for append-only records.
3. **Unknown keys are preserved, never rejected.** A pack written by a newer
   compiler must still load in an older reader.
4. **Unknown fields are ignored by readers.** See rule 3, applied to the
   individual record.
5. **The reader never writes.** A checker MUST NOT modify a pack it checks.
   Repair is the owner's decision, not the linter's.
6. **Evidence is mandatory for verified claims.** A pack that asserts
   something without a locator is a pack that cannot be checked.
7. **Absence of evidence is recorded, not implied.** A claim that has no
   evidence says so, in its status.
8. **A pack must be safe to share.** See §11.

## 2. Terminology

| Term | Meaning |
|---|---|
| **pack** | A directory conforming to this specification |
| **claim** | One atomic assertion, with an id, a status and evidence |
| **evidence** | A quote and a locator that supports a claim |
| **source** | A file, URL or document a pack was compiled from |
| **entity** | A named thing claims are about |
| **relation** | A typed edge between two entities |
| **contradiction** | A recorded conflict between two claims |
| **freshness** | The review state of a claim: when it was last checked and when it expires |
| **checker** | An implementation of this specification's rules |

## 3. Pack layout

A pack is a directory containing exactly these eight files:

```
pack/
├── manifest.json        identity, provenance and inventory
├── claims.jsonl         one JSON object per line: the claims
├── evidence.jsonl       one JSON object per line: the evidence
├── entities.json        the entities and their aliases
├── relations.json       the relations between entities
├── contradictions.json  recorded conflicts between claims
├── freshness.json       review windows and decay policy
└── README.md            a human-readable index
```

A conforming checker MUST report a pack missing any of these files as a
structural error. A conforming checker MAY accept additional files (for
example `verification.json`, the output of a previous check) and MUST ignore
files it does not recognise.

Implementations MAY place the pack anywhere on disk. Paths inside a pack are
always **relative and forward-slashed**, and are interpreted relative to the
**pack root** unless a tool explicitly says otherwise.

## 4. `manifest.json`

A JSON object.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `format_version` | string | yes | The version of this specification the pack conforms to. See §10. |
| `pack_id` | string | yes | A stable identifier for the pack. Lowercase, no spaces. |
| `title` | string | no | Human title. |
| `description` | string | no | One or two sentences on what the pack holds. |
| `generated_at` | string | no | ISO 8601 timestamp of generation. |
| `generator` | object | no | Free-form: `{"name": ..., "version": ..., "commit": ...}`. |
| `sources` | array | yes | The source list. See below. |
| `stats` | object | no | Counts. Informational; a checker MUST recompute rather than trust them. |
| `verification` | object | no | The result of the last check: `{"tool", "tool_version", "status", "checked_at"}`. |

A **source** is an object:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique within the pack. |
| `path` | string | yes | Path of the source, relative to the pack root. For a URL source, the URL. |
| `title` | string | no | Human title. |
| `kind` | string | no | `file`, `markdown`, `url`, `pdf`, `database`, … |
| `sha256` | string | no | Hex digest of the source content, when it can be computed. |
| `url` | string | no | The canonical location, for remote sources. |
| `modified_at` | string | no | ISO 8601 timestamp. |
| `aliases` | array of string | no | Other names the source is linked under. |
| `namespace` | string | no | The numbering space this source's numbers belong to. See §4.1. |
| `id` | string | no | The source's own number, when it has one. |

Source ids MUST be unique within the pack. A checker MUST report a duplicate
source id as an error.

### 4.1 Numbering spaces

A corpus may keep more than one numbering scheme: a global `C-001` and a
domain-local `C-001` in a sub-collection. That is legitimate, but it has to be
declared rather than inferred from where a file happens to sit, because a
checker cannot otherwise tell a deliberate second space from a file that was
copied and never cleaned up.

A source MAY carry a `namespace`. Sources without one belong to the default
namespace. Two sources carrying the same number **in the same namespace**
collide, and a checker MUST report that as an error.

Where a number is inferred from a filename rather than declared, it is only
inferred when the number is followed by an underscore (`C-001_Title.md`). A
filename that merely begins with digits and a hyphen (`acme-1077-pricing.md`)
is a document name, not a card number.

## 5. `claims.jsonl`

One JSON object per line, UTF-8, newline-terminated. Blank lines and lines
beginning with `#` MUST be ignored by readers.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique within the pack. |
| `text` | string | yes | The assertion itself, in one sentence. |
| `status` | string | yes | One of `asserted`, `verified`, `inferred`, `disputed`, `refuted`. |
| `confidence` | number | no | 0..1. A producer's own estimate. |
| `evidence` | array of string | no | Evidence ids backing this claim. |
| `entities` | array of string | no | Entity ids this claim is about. |
| `topics` | array of string | no | Topic labels. Used by freshness policy overrides. |
| `links` | array of object | no | References to files. See §5.1. |
| `notes` | string | no | Reasoning, caveats, or the resolution of a dispute. |
| `created_at` | string | no | ISO 8601 timestamp. |
| `updated_at` | string | no | ISO 8601 timestamp. |

Status semantics — a checker MUST enforce these:

| Status | Meaning | Requirement |
|---|---|---|
| `verified` | Confirmed against a source | MUST have at least one evidence record |
| `asserted` | Stated, not yet confirmed | SHOULD have evidence; a checker MUST report its absence as a warning |
| `inferred` | Derived by reasoning | MUST carry a rationale in `notes` |
| `disputed` | Two sources disagree | MUST be referenced by a contradiction entry |
| `refuted` | Contradicted by evidence | MUST be referenced by a contradiction entry |

A claim marked `verified` with no evidence is an **error**. This is the single
most important rule in the format: it is the difference between "compiled"
and "trustworthy".

### 5.1 Links

A link is an object:

| Field | Type | Meaning |
|---|---|---|
| `target` | string | The link as written: `[[Some Note]]`, `notes/file.md`, a URL. |
| `resolved` | string or null | The source path it resolves to, or `null` if unresolved. |

Resolution follows Obsidian's rules, in this order: exact path, exact path
plus `.md`, path suffix, basename, source alias. A checker MUST report a link
whose `resolved` value is null, or whose `resolved` value is not a path listed
in `manifest.sources`, as an error.

Entity names and aliases are a separate namespace. They resolve entity
references, never links to files: a link whose target is an entity name is a
broken link, and the checker SHOULD say so, because the fix is to move the
reference into the claim's `entities` field.

## 6. `evidence.jsonl`

One JSON object per line.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique within the pack. |
| `claim_id` | string | yes | The claim this evidence supports. |
| `source_id` | string | yes | The source it comes from. |
| `quote` | string | yes | The text that supports the claim. MUST NOT be empty. |
| `locator` | object | no | Where in the source: `{"path", "line_start", "line_end", "anchor"}`. |
| `quote_sha256` | string | no | Hex digest of the quote text. |
| `retrieved_at` | string | no | ISO 8601 timestamp of extraction. |

`claim_id` MUST reference an existing claim and `source_id` MUST reference an
existing source; a checker MUST report a violation of either as an error.

When `quote_sha256` is present it MUST equal the SHA-256 of the UTF-8 bytes of
`quote`. A mismatch means the quote was edited after it was recorded, and a
checker MUST report it as an error. This is the cheapest tamper-evidence
available and it costs one hash.

## 7. `entities.json`

A JSON object with an `entities` array.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique within the pack. |
| `name` | string | yes | The canonical name. |
| `type` | string | no | `person`, `org`, `product`, `concept`, `project`, … |
| `aliases` | array of string | no | Other names the same entity is written under. |
| `properties` | object | no | Free-form attributes. |

Aliases exist for one reason: the same organisation is written three ways
across a CRM, an inbox and a document, and a checker that cannot fold them
together will report a broken link every time.

## 8. `relations.json`

A JSON object with a `relations` array.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique within the pack. |
| `from` | string | yes | Entity id. |
| `to` | string | yes | Entity id. |
| `type` | string | yes | The relation type: `works_at`, `owns`, `competes_with`, … |
| `evidence` | array of string | no | Evidence ids that support the relation. |
| `claim_id` | string | no | The claim the relation was derived from. |
| `note` | string | no | Free text. |

Both endpoints MUST be existing entities.

## 9. `contradictions.json`

A JSON object with a `contradictions` array.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique within the pack. |
| `claims` | array of string | yes | The conflicting claim ids. At least two. |
| `description` | string | no | What the conflict is. |
| `status` | string | yes | `open` or `resolved`. |
| `resolution` | string | no | How it was settled. Required when `status` is `resolved`. |
| `detected_at` | string | no | ISO 8601 timestamp. |

A contradiction is a feature, not a defect. A pack that records its conflicts
is more trustworthy than one that has silently picked a winner.

## 10. `freshness.json`

A JSON object.

| Field | Type | Meaning |
|---|---|---|
| `policy` | object | `{"default_ttl_days": int, "per_topic": {topic: int}}` |
| `claims` | object | Map of claim id to a freshness entry |

A freshness entry:

| Field | Type | Meaning |
|---|---|---|
| `source_date` | string | When the underlying material was dated. |
| `reviewed_at` | string | When a human or agent last checked the claim. |
| `expires_at` | string | When the claim should be reviewed again. |
| `decay` | string | `linear`, `step`, or `none`. |
| `last_verified` | string | When the claim was last confirmed against its evidence. |

A claim whose `expires_at` is in the past MUST be reported as stale. A claim
with no `reviewed_at` whose age exceeds the applicable TTL MUST be reported as
stale. The applicable TTL is the per-topic override when the claim has that
topic, otherwise the default.

## 11. Sharing and hygiene

Packs are meant to travel: between tools, between teams, between vendors.
Two consequences follow, and a conforming checker SHOULD implement both.

- **Credentials MUST NOT appear in a pack.** A pack that contains something
  shaped like an API key, a token or a private key MUST be reported as an
  error.
- **Personal contact details SHOULD be reported.** An email address or phone
  number in a pack is usually a mistake; it is reported as a warning.

## 12. Action records

Separately from the pack, ctxverify defines a small record format for
**verifying that reported work actually happened**. It is specified here
because the same reasoning applies: a report is a claim, and a claim deserves
evidence.

An action record is one JSON object per line:

```json
{"id": "a-001", "action": "archived", "path": "notes/C-001.md"}
{"id": "a-002", "action": "moved", "path": "new/C-001.md", "from": "old/C-001.md"}
{"id": "a-003", "action": "wrote", "path": "out.md", "sha256": "…"}
{"id": "a-004", "action": "deleted", "path": "notes/old-draft.md"}
{"id": "a-005", "action": "archived", "paths": ["a.md", "b.md"], "count": 2}
```

`action` MUST be one of `archived`, `moved`, `deleted`, `wrote`, `exists`.

Verification rules:

| Action | The filesystem must show |
|---|---|
| `archived`, `exists`, `wrote` | the path exists |
| `deleted` | the path does not exist |
| `moved` | the new path exists **and** the `from` path does not |
| any | `count`, when given, equals the number of listed paths |
| any | `sha256`, when given, equals the SHA-256 of the file's bytes |

Any mismatch MUST be reported as an error. This is the check that catches the
failure mode that motivates it: an agent reporting eight files archived, none
of which moved.

## 13. Versioning

`format_version` is `MAJOR.MINOR`.

- **Additive changes** — a new optional field, a new file — bump MINOR.
  Readers MUST ignore fields they do not recognise.
- **Breaking changes** — removing a field, changing its meaning, changing the
  meaning of a status — bump MAJOR.
- A reader MUST refuse a pack whose MAJOR version it does not implement, and
  MUST NOT silently reinterpret it.
- MINOR versions of the format are compatible with each other within a MAJOR.
  A reader that implements MAJOR `n` MUST accept any MINOR of `n`, and MAY
  report that the pack declares a newer minor than the reader knows.

Implementations SHOULD expose their own version separately from the format
version they support.

## 14. Conformance

A **conforming checker** for format version X:

1. Loads a pack without modifying it.
2. Reports a structural error for a missing required file, an unparsable
   file, a collection file with the wrong top-level shape, or an unsupported
   MAJOR version.
3. Implements the required rules: `pack.structure`, `provenance.missing`,
   `provenance.dangling`, `provenance.quote`, `links.broken`,
   `ids.duplicate`, `ids.collision`, `status.inconsistent`,
   `contradiction.unresolved`, `freshness.stale`, `duplicate.claim`.
4. May implement additional rules. They MUST be reported under their own
   identifiers so that a user can tell a required rule from an extra one.
5. Exits 0 when no error-level finding is present, 1 when at least one is
   present, and 2 when the pack could not be read at all. A severity filter
   MUST NOT change the exit code: the exit code reflects every finding the
   run produced.
6. Produces a machine-readable report alongside the human-readable one, and
   both agree on the verdict.

A **conforming producer** writes the eight files, keeps ids unique, backs
every `verified` claim with evidence, and records sources it actually read.

## 15. Change log for this specification

### 0.1 — 2026-11-05

First release. Eight-file layout; claim/evidence/source/entity/relation/
contradiction/freshness records; Obsidian-style link resolution; the action
record format (§12); the conformance requirements (§14).
