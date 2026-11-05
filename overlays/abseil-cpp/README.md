# Chromium Abseil compatibility update

Existing BCR module `abseil-cpp`, proposed version
`20250814.1.chromium142`, compatibility level 1. Reuses upstream native Bazel
rules and BCR 20250814.1 release archive/SRI.

Ports Chromium's three local patches: enable hardened mode, stop exporting
unprefixed annotation macros, remove generic stacktrace static initialization.
Keeps BCR's inline namespace so Protobuf and Chromium share one implementation.
`@abseil-cpp//absl/chromium:absl` exposes Chromium's exact component dependency
facade without relaxing internal target visibility.

Release-mode test verifies fatal Span/InlinedVector bounds checks, annotation
isolation, real hash-map/formatting behavior, and x86_64 stack traces. Consumer
registers hermeticbuild LLVM. CMake manifest edits mirror Chromium patches;
CMake never runs.

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py --source-registry overlays/abseil-cpp/bcr --target-registry "$registry" --module abseil-cpp --version 20250814.1.chromium142
cd overlays/abseil-cpp/tests
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build //:hardening_test
```

No BCR publication yet. Complete Chromium API compatibility remains under test.
