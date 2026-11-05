---
name: Bug report
about: Something ctxverify reports that is wrong, or something it fails to report
title: ""
labels: bug
assignees: ""
---

**What happened**

A rule fired on a pack it should not have, or a rule stayed silent on a pack
it should have caught.

**The pack**

If you can share it, attach the eight files or a link. If not, the smallest
reproduction you can manage: the claim, the evidence record, and the manifest
source it points at.

**What you ran**

```
ctxv check <pack> --format json
```

Paste the JSON output. It names the rule, the severity, the location and the
hint.

**What you expected**

**Which version**

```
ctxv --version
```

**Anything else**

The rule catalogue is in `docs/rules.md`. If a rule is doing something you
did not expect, the rule id in the output is the fastest way to find its
documentation.
