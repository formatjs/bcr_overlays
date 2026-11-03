# Chromium native Bazel overlay

Native Bazel migration for [chromium/chromium](https://github.com/chromium/chromium).
Layout follows [perplexityai/rocksdb](https://github.com/perplexityai/rocksdb):
maintained `bcr/overlay`, blank-version module templates, immutable registry staging,
separate development harness and consumer smoke build.

**Bootstrap stage. Full browser does not build yet.** No `chrome` target exists.
No CMake, GN, Ninja, gclient, or foreign-build wrapper runs during a build.

## Source and dependencies

Initial source baseline: Chromium **142.0.7444.59**, commit
`4b8153ab58d3c3f4c9f7e4baad9616ecf80db5fa`. This is a migration baseline,
not a recommendation to run an old browser. Archive checksum was computed from
the downloaded GitHub archive. Chromium's archive excludes DEPS-managed repositories;
each required dependency must become a pinned Bazel repository or BCR dependency.

Implemented native targets:

- `@chromium//build:build_config` and `:buildflag`.
- `buildflag_header` macro, using `ctx.actions.write` and `cc_library`.
- `@chromium//third_party/modp_b64`.
- `@chromium//base/third_party/cityhash`.
- `@chromium//base/third_party/superfasthash`.
- `@chromium//base/third_party/icu:icu_utf` (Chromium's standalone UTF macros, not full ICU).
- `@chromium//base/third_party/double_conversion`, using BCR `double-conversion`.

GoogleTest also comes from BCR. Double Conversion consumers use canonical
`double-conversion/...` headers. Existing Chromium consumers still need their
vendored include paths migrated before they can use that dependency. Its BCR
version differs from Chromium's 2021 snapshot; full Chromium compatibility is
not established by the foundation tests. Chromium's CityHash has a private
namespace, so it retains upstream's bundled sources.

## Build

Run commands below from `overlays/chromium`.

Bazel 9.2.0 pinned; published module requires Bazel 8+. Linux x86_64 is the first
validation platform. The development harness uses the host C++ toolchain;
published module leaves toolchain selection to its consumer.

```sh
bazel build //:foundation
bazel test //:native_foundation_test
python3 tests/validate_bcr.py
```

Tests cover RFC 4648 vectors, malformed Base64, binary data, UTF-8 supplementary
characters and invalid sequences, CityHash, BCR Double Conversion linkage and
generated boolean, numeric and string flags.

## Local registry

```sh
registry=$(mktemp -d)
python3 ../../tools/stage_bcr_entry.py --source-registry bcr \
  --target-registry "$registry" --module chromium --version 142.0.7444.59
cd tests/bcr
bazel run --registry="file://$registry" --registry=https://bcr.bazel.build //:smoke_test
```

Proposed module API, available through a staged registry only:

```starlark
bazel_dep(name = "chromium", version = "142.0.7444.59")
```

Nothing has been published to BCR. Presubmit currently builds foundation targets;
it does not validate a browser. Maintainer metadata must be filled before BCR
submission. See [migration plan](native-browser.md).
Missing dependency overlays and existing BCR alternatives are recorded in the
[dependency audit](../../docs/dependency-overlays.md).

## License

Overlay code: BSD-3-Clause. Upstream Chromium and bundled third-party files retain
their own licenses. Registry staging script adapted from perplexityai/rocksdb
(Apache-2.0); see `../../NOTICE` and `../../tools/LICENSE`.
