# ipcz native Bazel overlay

Proposed module: `ipcz@0.0.0.chromium142`, pinned to Chromium 142.0.7444.59
(commit `4b8153ab58d3c3f4c9f7e4baad9616ecf80db5fa`). Chromium's
`third_party/ipcz` is the canonical ipcz repository.

- `@ipcz//:ipcz`: 36 core C++ sources and two upstream standalone support sources.
- `@ipcz//:headers`: public C API.
- `@ipcz//:static_api_header`: `ipcz/api.h` for static-library API discovery.
- `@ipcz//:reference_drivers`: original synchronous reference driver, test-only.
- `@ipcz//bazel:ipcz.bzl`: `ipcz_library` accepts a `chromium_base` target to build
  the original Chromium implementation. No Chromium module dependency or cycle.

Native Bazel C++ actions only. Source lists and compiler flags come from the
captured Linux graph. Optimization, stack protection and automatic-variable
initialization remain enabled. Standalone builds select `IPCZ_STANDALONE` and
stock BCR Abseil; Chromium builds use the caller's base implementation and its
shared Abseil dependency. Forwarding headers preserve original include paths.
No upstream source edits.

The source archive is the same immutable Chromium archive used by the Chromium
module, allowing repository-cache reuse. It also supplies the original platform
configuration headers needed by standalone support. Only ipcz and those headers
enter compile actions.

## Validate

From repository root:

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py --source-registry overlays/ipcz/bcr \
  --target-registry "$registry" --module ipcz --version 0.0.0.chromium142
cd overlays/ipcz/tests
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build //:ipcz_test
```

Consumer registers hermeticbuild LLVM `llvm@0.8.26`. Published library leaves
compiler selection to consumers. Linux x86_64 supported initially.

Tests connect real broker/client nodes through the original synchronous driver,
transfer a 65 KB binary message, reject insufficient receive capacity without
consuming data, transfer a portal and exchange data through it, observe peer
closure, and reject invalid API input. Chromium runs the same test source against
its base-backed variant. Chromium's separate Mojo runtime test also checks its
actual driver and generated RPC across processes. Browser assembly remains
pending.

Regenerate source inventory and Abseil forwarding headers:

```sh
python3 overlays/ipcz/tools/import_sources.py \
  overlays/chromium/native/linux_x64.json.gz /path/to/chromium
```

No module published to BCR yet. Maintainers recorded in [bcr/metadata.json](bcr/metadata.json).
