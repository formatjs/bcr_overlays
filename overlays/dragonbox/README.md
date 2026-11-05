# Dragonbox native Bazel overlay

Pinned to `6c7c925b571d54486b9ffae8d9d18a822801cbda` (1.1.3), matching
V8's Chromium 142 baseline. No Dragonbox module exists in the audited BCR tree.

Public target: `@dragonbox//:dragonbox`. Exposes upstream's header-only decimal
conversion algorithm through canonical `dragonbox/dragonbox.h` includes.
Native Bazel; no generators or foreign build backend. V8's consumer test covers
float-to-string round trips, including subnormals and maximum finite doubles.

Stage independently with `tools/stage_bcr_entry.py`, module `dragonbox`, version
`1.1.3`. See [V8](../v8) for combined local-registry validation.
No BCR publication yet; maintainers recorded in [bcr/metadata.json](bcr/metadata.json).
