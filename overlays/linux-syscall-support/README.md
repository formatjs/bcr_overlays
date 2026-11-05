# Linux Syscall Support native Bazel overlay

Chromium 142's exact [LSS](https://chromium.googlesource.com/linux-syscall-support)
revision `ed31caa60f20a4f6569883b2d752ef7522de51e0`.
Proposed module version: `0.0.0-20240201-ed31caa`.

`@linux-syscall-support//:linux-syscall-support` exports the original header,
without source patches or global syscall configuration. Linux only; initial
validation uses x86_64 and hermeticbuild LLVM.

Stable CitizenFX GitHub mirror archive matches all 22 files from the exact
GoogleSource revision. Source SRI pins archive bytes. GoogleSource archive
metadata changed between two downloads, so its generated archive is unsuitable
for a fixed checksum.

Standalone test uses real process/thread IDs, `/proc/self/stat` reads and errno
handling. No syscall mocks.

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py --source-registry overlays/linux-syscall-support/bcr \
  --target-registry "$registry" --module linux-syscall-support --version 0.0.0-20240201-ed31caa
cd overlays/linux-syscall-support/tests
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build //:syscall_test
```

No BCR publication yet. Maintainers recorded in [bcr/metadata.json](bcr/metadata.json).
