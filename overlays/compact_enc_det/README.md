# Compact Encoding Detection native Bazel overlay

Chromium 142's exact [CED](https://github.com/google/compact_enc_det) revision
`ba412eaaacd3186085babcd901679a48863c7dd5`.
Proposed version: `0.0.0-20190221-ba412ea`.

`@compact_enc_det//:ced` compiles four original C++ sources and 15 headers.
Preserves Chromium's `COMPILER_GCC`, `HTML5_MODE` and release/hardening settings.
Static linkage matches Chromium's hidden-symbol configuration. No source patches
or foreign-build backend.

Independent tests cover UTF-8, Shift-JIS, ISO-2022-JP and HTML5 UTF-16 handling.
Confidence is required only for unambiguous fixtures. Upstream reports one-byte
lookahead in its consumed-byte count. Consumer registers hermeticbuild LLVM.

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py --source-registry overlays/compact_enc_det/bcr \
  --target-registry "$registry" --module compact_enc_det --version 0.0.0-20190221-ba412ea
cd overlays/compact_enc_det/tests
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build //:encoding_test
```

Regenerate source configuration from Chromium's pinned graph:

```sh
python3 overlays/compact_enc_det/tools/import_sources.py \
  overlays/chromium/native/linux_x64.json.gz /path/to/pinned/compact_enc_det \
  --arm64-graph overlays/chromium/native/linux_arm64.json.gz \
  --darwin-arm64-graph overlays/chromium/native/darwin_arm64.json.gz \
  --windows-amd64-graph overlays/chromium/native/windows_amd64.json.gz \
  --windows-arm64-graph overlays/chromium/native/windows_arm64.json.gz
```

No BCR publication yet. Maintainers recorded in [bcr/metadata.json](bcr/metadata.json).
