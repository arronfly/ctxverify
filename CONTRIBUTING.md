# Contributing to ctxverify

## Setup

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

ctxverify itself has no runtime dependencies. The `dev` extra installs the test
dependencies only.

## Running the tests

```sh
PYTHONPATH=src python -m unittest discover -s tests -t .
```

To check the bundled examples after a change:

```sh
PYTHONPATH=src python -m ctxverify check examples/clean-pack
PYTHONPATH=src python -m ctxverify check examples/broken-pack
```

The first must exit 0 and the second must exit 1.

## Adding a new check

1. Implement the check in `src/ctxverify/checks/`, decorated with
   `@register("<rule id>")`.
2. Import the module at the bottom of `src/ctxverify/checks/__init__.py` so the
   decorator runs.
3. Add the rule to `RULES` in `src/ctxverify/rules.py` with the same stable id,
   a severity, a category, a title and a one-line description. Rule ids are part
   of the public contract: CI configurations select rules by id, so do not
   rename an id once it has shipped.
4. Add a test under `tests/` that fails before the check and passes after it.
5. Document the rule in `docs/rules.md`.

## Changing the format

The format version is `FORMAT_VERSION` in `src/ctxverify/model.py`.

- Bump it whenever the meaning of a file, a field or a status changes.
- Add the new version to `SUPPORTED_FORMAT_VERSIONS`.
- Keep old versions readable. A pack written against an older version must
  still load, and unknown keys are preserved rather than rejected, so an older
  linter can check a newer pack.
- Update `SPEC.md` and the version noted in `CHANGELOG.md`.

## Commits and pull requests

- One logical change per commit. Use an imperative subject line of 72
  characters or fewer, prefixed with the area touched, for example
  `checks: reject empty evidence quotes`.
- Run the tests and check both example packs before opening a pull request.
- Describe what changed and why in the pull request body. Link the issue if
  there is one.
- Do not bump the version or edit released sections of `CHANGELOG.md` in a
  feature pull request; releases are cut separately.
- By contributing you agree that your contribution is licensed under the
  Apache License, Version 2.0, the same license as the code.
