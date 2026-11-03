# WebRTC native Bazel overlay

Status: planned. Native implementation, archive checksum, tests and release version
remain pending. This directory does not provide a buildable module yet.

Upstream: [WebRTC](https://webrtc.googlesource.com/src.git), revision
`29d6eabaf0b5c1a62af6e7fd03adebf5e1a446e8`, matching Chromium 142.0.7444.59's DEPS.
Machine-readable pin: [upstream.json](upstream.json).

BCR module name: `webrtc`. Maintain this module's own `bcr/` directory,
versions and presubmit. Once implemented, publish separately using the shared
[staging tool](../../tools/stage_bcr_entry.py). An empty version list deliberately
prevents publishing this scaffold.

Build rules and generators must be native Bazel. Reuse compatible BCR dependencies.
No CMake, GN, Ninja or foreign-build wrappers.
