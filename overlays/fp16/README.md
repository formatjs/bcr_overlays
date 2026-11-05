# FP16 BCR compatibility extension

Extends existing BCR module `fp16`; no second module name. Same source archive
and SHA-256 as BCR `0.0.0-20210320-0a92994`. Proposed overlay revision:
`0.0.0-20210320-0a92994.bcr.1`.

Existing BCR BUILD uses native `cc_library`, removed in Bazel 9. This overlay
loads `cc_library` from `rules_cc`, exposes upstream headers with canonical
includes, preserves compatibility level 1. No source changes.

Public target: `@fp16//:fp16`. V8's consumer test covers half-float rounding,
maximum finite half, smallest half subnormal. This tests the adopted header
API; it does not establish full Chromium FP16 fork equivalence.

Stage independently with `tools/stage_bcr_entry.py`. See [V8](../v8) for combined
local-registry validation. Submit as an update to existing BCR module.
Maintainers recorded in [bcr/metadata.json](bcr/metadata.json); nothing published.
