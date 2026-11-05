# Producing a context pack

This guide is for people who write a compiler, an exporter or a script that produces packs. It describes the file layout, the fields each record accepts, and the parts of the format that carry meaning for a reviewer. It is practical, not normative; the normative specification is `SPEC.md`.

The design goal is that a pack is boring. It is a directory of JSON and JSONL files. It can be committed, zipped, diffed, copied to another machine and read without a database. Anything that reads JSON can read a pack.

## The eight required files

A pack is a directory with exactly these files present. `ctxverify` reports `pack.structure` when one is missing.

| File | Encoding | Purpose |
|---|---|---|
| `manifest.json` | JSON object | Identity, format version, generator, source inventory |
| `claims.jsonl` | JSONL | One atomic assertion per line |
| `evidence.jsonl` | JSONL | One quote and locator per line, tied to a claim and a source |
| `entities.json` | JSON object | Named things and their aliases |
| `relations.json` | JSON object | Typed edges between entities |
| `contradictions.json` | JSON object | Pairs of claims that cannot both be true |
| `freshness.json` | JSON object | Review policy and per-claim review state |
| `README.md` | UTF-8 text | Human overview |

JSONL means one JSON object per line. Blank lines and lines whose first non-whitespace character is `#` are skipped by the loader. The writer emits one compact object per line and never emits comments.

The format version implemented by this build is `0.1`. Compatibility is decided by the major version: a pack that declares the same major with a newer minor, such as `0.2`, is read and produces an `info` finding saying the pack declares a newer minor; a different major, such as `1.0`, fails `pack.structure` with an "unsupported format_version" message.

A pack may contain additional files. This build ignores files it does not recognise, with one exception: `verification.json`, holding the output of a previous check, which the loader reads. See the `manifest.json` section below.

Unknown keys on claims, evidence, sources, entities, relations, contradictions and the manifest survive a load and write cycle, so a pack written by a newer compiler stays intact when an older linter writes it back.

## manifest.json

```json
{
  "format_version": "0.1",
  "pack_id": "example-clean",
  "title": "Example — a pack that passes",
  "description": "A minimal, well-formed context pack.",
  "generated_at": "2026-11-05T00:00:00Z",
  "generator": {"name": "handwritten", "version": "1.0"},
  "sources": [
    {
      "id": "src-001",
      "path": "sources/notes.md",
      "title": "Working notes",
      "kind": "file",
      "sha256": null,
      "url": null,
      "modified_at": null
    }
  ],
  "stats": {"claims": 1, "evidence": 1, "entities": 0, "relations": 0, "contradictions": 0, "sources": 1},
  "verification": {}
}
```

| Field | Required | Meaning |
|---|---|---|
| `format_version` | Required by the spec | Defaults to `0.1` when absent. The major version must match this build's `0.1`; a newer minor is read with an `info` finding |
| `pack_id` | Required by the spec | Stable identifier for the pack, lowercase with no spaces |
| `title`, `description` | Optional | Human-facing text |
| `generated_at` | Optional | ISO 8601 timestamp |
| `generator` | Optional | Object such as `{"name": ..., "version": ...}` |
| `sources` | Required by the spec | The inventory that links and evidence resolve against |
| `stats` | Optional | Inventory counts. Written by the writer. `ctxverify` recomputes counts for its report instead of trusting this field |
| `verification` | Optional | Result of a previous check, conventionally `{"tool", "tool_version", "status", "checked_at"}`. Carried through; no check reads it. A pack's `verification.json` is merged into this object on load, with the manifest's own keys winning |

Each source has an `id`, a `path`, and optional `title`, `kind`, `sha256`, `url` and `modified_at`. `kind` defaults to `"file"`. The `path` is what claim links resolve against, so it should match the path you would write in a wikilink. The checker never opens the source file, so a source path can be recorded even when the file is not present in the pack.

A source may carry two extra fields that affect checking:

| Field | Meaning |
|---|---|
| `aliases` | An array of alternative names. A claim link to one of them resolves to this source, the way Obsidian resolves a note's frontmatter aliases |
| `namespace` | A numbering space for `ids.collision`. Numbers are compared within a namespace; sources without one share the default namespace |

`verification.json` is an optional file. When present, the loader reads it into the manifest's `verification` object, adding to what the manifest already has (the manifest's own keys take precedence). It is informational and never changes the verdict.

## claims.jsonl

```json
{"id": "clm-001", "text": "A context pack is a portable container for the knowledge an agent is given.", "status": "verified", "confidence": 1.0, "evidence": ["ev-001"], "entities": ["ent-001"], "topics": ["ctxverify"], "links": [{"target": "[[C-002_Evidence]]", "resolved": "concepts/C-002_Evidence.md"}], "notes": null, "created_at": "2026-11-01T00:00:00Z", "updated_at": "2026-11-05T00:00:00Z"}
```

| Field | Meaning |
|---|---|
| `id` | Unique within the claims collection. Conventional prefix: `clm-` |
| `text` | One atomic assertion. Empty text is a `status.inconsistent` error |
| `status` | One of `asserted`, `verified`, `inferred`, `disputed`, `refuted`. Defaults to `asserted` |
| `confidence` | Optional number. Carried, not interpreted by any check |
| `evidence` | List of evidence ids that support this claim |
| `entities` | List of entity ids mentioned by this claim |
| `topics` | List of topic strings, used by freshness policy overrides |
| `links` | List of link targets. A string is normalised to `{"target": str, "resolved": null}` |
| `notes` | Required for `inferred` claims. Free text |
| `created_at`, `updated_at` | ISO 8601 timestamps, used as freshness fallbacks |

Keep one fact per claim. A sentence with "and" in it is usually two claims. Claim-level atomisation is the point of the format: it is what lets one assertion map to one quote and one review state.

## evidence.jsonl

```json
{"id": "ev-001", "claim_id": "clm-001", "source_id": "src-001", "quote": "A context pack is a portable container for the knowledge an agent is given.", "locator": {"path": "sources/notes.md", "line_start": 3, "line_end": 3}, "quote_sha256": "e78ad35b4aa7a0f107349ce5c3cacb61e0d9618a842af7f41876d9c9b7f2d542", "retrieved_at": "2026-11-05T00:00:00Z"}
```

| Field | Meaning |
|---|---|
| `id` | Unique within the evidence collection. Conventional prefix: `ev-` |
| `claim_id` | The claim this evidence supports. Also listed in that claim's `evidence` |
| `source_id` | A source id from `manifest.json` |
| `quote` | The text from the source. Must be non-empty |
| `locator` | Free-form object. The convention is `path`, `line_start`, `line_end`, and optionally `anchor` |
| `quote_sha256` | Hex sha256 of the UTF-8 encoding of `quote`. Optional but recommended |
| `retrieved_at` | ISO 8601 timestamp |

The relationship is bidirectional: the claim lists the evidence id, and the evidence names the claim id. `ctxverify` checks both directions. If they disagree, `status.inconsistent` fires.

## entities.json, relations.json, contradictions.json

Entities:

```json
{
  "entities": [
    {"id": "ent-001", "name": "Locator", "type": "concept", "aliases": ["locators"], "properties": {}}
  ]
}
```

Relations:

```json
{
  "relations": [
    {"id": "rel-001", "from": "ent-001", "to": "ent-002", "type": "depends_on", "evidence": ["ev-001"], "claim_id": "clm-001", "note": null}
  ]
}
```

The reader also accepts `from_id` and `to_id` as aliases for `from` and `to`. The writer emits `from` and `to`. Set `type` explicitly; the reader falls back to `related_to` when it is absent.

For `entities.json`, `relations.json` and `contradictions.json`, the reader requires an object with the collection key. A bare array, an empty object or a wrong key produces a `pack.structure` error naming the file and the expected key, and the collection is read as empty. `freshness.json` must likewise be an object; anything else is a `pack.structure` error rather than an empty policy.

Contradictions:

```json
{
  "contradictions": [
    {
      "id": "con-001",
      "claims": ["clm-001", "clm-002"],
      "description": "One source says the wiki ships unchecked, another says it is checked before shipping.",
      "status": "open",
      "resolution": null,
      "detected_at": "2026-11-05T00:00:00Z"
    }
  ]
}
```

The spec requires `status` to be `open` or `resolved`; the reader defaults it to `"open"` when absent. A contradiction needs at least two claim ids, and every id must exist. A resolved contradiction needs non-empty `resolution` text.

## freshness.json

```json
{
  "policy": {
    "default_ttl_days": 180,
    "per_topic": {"ctxverify": 90}
  },
  "claims": {
    "clm-001": {
      "source_date": "2026-11-01",
      "reviewed_at": "2026-11-05",
      "expires_at": "2027-02-01",
      "decay": "linear",
      "last_verified": "2026-11-05"
    }
  }
}
```

`policy.default_ttl_days` applies when no topic override matches. `policy.per_topic` maps a topic string to a TTL in days. For each claim, the first topic in the claim's `topics` list that has an override wins; otherwise the default applies. A claim with no matching policy and no default is not age-checked.

Per-claim fields:

| Field | Meaning |
|---|---|
| `source_date` | When the underlying source was written. Falls back to claim `updated_at`, then `created_at` |
| `reviewed_at` | When a human or process last reviewed the claim. When set, the TTL age check is skipped |
| `expires_at` | Hard expiry. Checked independently of the TTL |
| `decay` | Carried, not interpreted. The spec names `linear`, `step` and `none` |
| `last_verified` | Carried, not interpreted |

To make a stale claim fresh, either move `expires_at` forward or record `reviewed_at`. Shortening the TTL does not make the claim fresher; it makes more claims stale.

## A worked example

The clean example pack contains two claims. This is the first one in full, across the three files that participate:

`claims.jsonl`:

```json
{"id": "clm-001", "text": "A context pack is a portable container for the knowledge an agent is given.", "status": "verified", "confidence": 1.0, "evidence": ["ev-001"], "topics": ["ctxverify"]}
```

`evidence.jsonl`:

```json
{"id": "ev-001", "claim_id": "clm-001", "source_id": "src-001", "quote": "A context pack is a portable container for the knowledge an agent is given.", "locator": {"path": "sources/notes.md", "line_start": 3, "line_end": 3}, "quote_sha256": "e78ad35b4aa7a0f107349ce5c3cacb61e0d9618a842af7f41876d9c9b7f2d542", "retrieved_at": "2026-11-05T00:00:00Z"}
```

`manifest.json`, source entry:

```json
{"id": "src-001", "path": "sources/notes.md", "title": "Working notes", "kind": "file"}
```

Read it as a chain:

1. `clm-001` is marked `verified`, so it must have evidence.
2. Its `evidence` list contains `ev-001`.
3. `ev-001` exists, and its `claim_id` points back at `clm-001`.
4. `ev-001.source_id` points at `src-001`, which exists in the manifest.
5. The quote is non-empty.
6. `quote_sha256` equals the sha256 of the quote text.
7. If the claim had links, each one would have to resolve to a manifest path.

Break any link in that chain and a rule fires: `provenance.missing`, `provenance.dangling`, `provenance.quote`, or `links.broken`.

## Writing evidence that survives review

**Quote the smallest passage that supports the claim.** A quote that spans three paragraphs is hard to check and easy to over-read. If a claim needs two separate passages, use two evidence records.

**Copy the quote exactly.** The sha256 covers the exact UTF-8 string, including whitespace and punctuation. If you normalise whitespace before hashing, hash the normalised text and keep that same text in `quote`. Never edit a quote after recording its hash; `provenance.quote` will catch it, and a human reviewer should treat the mismatch as a signal that something changed.

**Leave `quote_sha256` out only if you have a reason.** Empty quotes are always an error. A quote without a hash is accepted, but the hash is what detects later tampering.

**Use a locator a human can follow.** The convention is `{"path": "sources/paper.md", "line_start": 12, "line_end": 12}`. Line numbers are 1-based by convention. The checker does not validate the locator against the source file and does not verify that the line range contains the quote; that is the compiler's job. A locator that is wrong but internally harmless will pass the linter. Treat the linter as one gate, not the only one.

**Record `retrieved_at` when the source can change.** A URL or a live document has a retrieval time. A file in the pack may not need one, but recording it costs nothing and helps a reviewer reconstruct the state.

**Do not smuggle context into the quote.** The quote is evidence for one claim. If you need to explain the quote, use `notes` on the claim or `description` on a contradiction.

## Using claim statuses

| Status | Obligation | What it means |
|---|---|---|
| `asserted` | None. Missing evidence produces a warning | The compiler or author believes it, but has no locatable source |
| `verified` | At least one evidence record. Missing evidence is an error | A source supports it and the evidence chain is recorded |
| `inferred` | Non-empty `notes` explaining the reasoning. Missing notes is a warning | Derived from other claims rather than quoted directly |
| `disputed` | A contradiction entry must reference the claim. Missing entry is a warning | There is a known competing claim |
| `refuted` | A contradiction entry must reference the claim | The claim is known to be false, and the pack keeps the record of why |

An unknown status is an error. Do not invent statuses; add a field in `extra` if you need compiler-specific state.

## Using contradictions

Record a contradiction when two claims cannot both be true. Name both claims. Write a description that a reader can evaluate without opening either source. Leave `status` as `open` while the conflict is unresolved; this produces a warning, which is intentional. When you resolve it, set `status` to `resolved` and write the resolution. If one side is wrong, mark that claim `refuted` and keep the contradiction entry that records why.

Do not use contradictions for tension, uncertainty or scope differences. A contradiction is a hard incompatibility. A claim that is merely low-confidence should carry a lower `confidence` value or be marked `inferred`.

## IDs and numbering

Identifiers are strings. Prefixes are conventional, not enforced:

| Prefix | Collection |
|---|---|
| `clm-` | Claims |
| `ev-` | Evidence |
| `src-` | Sources |
| `ent-` | Entities |
| `rel-` | Relations |
| `con-` | Contradictions |

Ids must be unique within their collection and non-empty. They do not have to be unique across collections.

Numbered files are a separate convention. If a source's filename starts with `PREFIX-123` followed by an underscore, or if the source carries an `id`, `number` or `编号` field of that shape, `ids.collision` treats that number as owned by the file. The underscore requirement is deliberate: `acme-1077-transmission-pricing.md` is a document id, not card number 1077. It also means a file named exactly `C-001.md` carries no number from its filename; give it an `id` or `number` field if it should.

One number must map to one file within a namespace. A source without a `namespace` belongs to the default namespace, where any two files carrying the same number still collide. Declaring a `namespace` on each source is how you say that two directories are two deliberate numbering spaces. If you renumber, update every reference.

## Writing an adapter

An adapter reads your compiler's output and produces a `Pack` in memory. The writer lays it out as the eight files.

```python
from ctxverify.model import Claim, Entity, Evidence, Manifest, Pack, Source
from ctxverify.writer import evidence_record, write_pack

quote = "Every claim needs a locator that points back to a place in a source."

pack = Pack(
    root=".",
    manifest=Manifest(
        pack_id="my-compiler",
        title="My compiler output",
        sources=[Source(id="src-001", path="sources/paper.md", title="Paper")],
    ),
    claims=[
        Claim(
            id="clm-001",
            text="A claim needs a locator.",
            status="verified",
            evidence=["ev-001"],
            entities=["ent-001"],
        )
    ],
    evidence=[
        Evidence.from_dict(
            evidence_record(
                "ev-001",
                "clm-001",
                "src-001",
                quote,
                {"path": "sources/paper.md", "line_start": 12, "line_end": 12},
            )
        )
    ],
    entities=[Entity(id="ent-001", name="Locator", type="concept")],
)
write_pack(pack, "out")
```

Run it, then check the result:

```bash
python build.py
ctxv check out
```

That snippet produces a pack with one claim, one evidence record, one entity and one source. It passes with zero findings.

A practical adapter sequence:

1. **Inventory the sources.** Give every source a stable id and the path you want links to resolve against. Put them in `manifest.sources`.
2. **Emit claims.** One assertion per claim. Choose a status that matches the obligation table. If you cannot attach a quote, use `asserted` or `inferred`, not `verified`.
3. **Emit evidence.** For every `verified` claim, call `evidence_record(...)`, which fills `quote_sha256` for you. Keep `claim_id` and `source_id` in sync.
4. **Emit entities and relations.** Entity names and aliases resolve entity references, not links; keep them stable anyway, because claims and relations point at entity ids. If links should resolve to a name that is not the file path, put an `aliases` array on the source.
5. **Emit contradictions.** If your compiler detects conflicting sources, record the contradiction. Do not silently pick a winner.
6. **Emit freshness.** Choose a default TTL that fits the domain. Add `per_topic` overrides for fast-moving topics. Record `reviewed_at` when a human reviews.
7. **Write and check.** `write_pack(pack, out)` then `ctxv check out`. Fix what it reports before shipping.

Two reference adapters ship with the project:

- `src/ctxverify/adapters/obsidian.py` maps one note to one claim, with the note summary or first paragraph as the quote. It preserves the link structure.
- `src/ctxverify/adapters/llmwiki.py` reads citation markers of the form `^[source.md:42-58]` and turns each cited paragraph into evidence. It records every citation and adds a source entry for the cited filename. It does not drop a citation whose source file is absent from the project; no check stats source files, so such a citation survives as a recorded reference.

## Conformance checklist

- Eight files present, all parse.
- `manifest.format_version` is `0.1`.
- Every source has a unique `id` and a `path`.
- Every claim has a unique id, non-empty text, and a known status.
- Every `verified` claim lists at least one existing evidence record.
- Every evidence record has a non-empty quote, an existing `claim_id` and an existing `source_id`, and its `claim_id` points back at the claim that lists it.
- Every claim link resolves to a manifest path.
- Every entity id referenced by a claim or relation exists.
- Every contradiction names at least two existing claims; resolved contradictions carry resolution text.
- Freshness policy exists when claims have source dates; review dates are current.
- No credentials or personal contact details in claim text, notes, quotes, entity names, relation notes, contradiction descriptions or README.

Run `ctxv check <pack>` to confirm the machine-checkable parts. The rest is editorial judgment.
