# ANGLE native Bazel overlay

Status: planned. Native implementation, archive checksum, tests and release version
remain pending. This directory does not provide a buildable module yet.

Upstream: [ANGLE](https://chromium.googlesource.com/angle/angle.git), revision
`e5b338502c7c65bd38d4695bc557938ca4cc3aa7`, matching Chromium 142.0.7444.59's DEPS.
Machine-readable pin: [upstream.json](upstream.json).

BCR module name: `angle`. Maintain this module's own `bcr/` directory,
versions and presubmit. Once implemented, publish separately using the shared
[staging tool](../../tools/stage_bcr_entry.py). An empty version list deliberately
prevents publishing this scaffold.

Build rules and generators must be native Bazel. Reuse compatible BCR dependencies.
No CMake, GN, Ninja or foreign-build wrappers.
