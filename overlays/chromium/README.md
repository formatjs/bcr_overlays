# Chromium native Bazel overlay

Native Bazel migration for [chromium/chromium](https://github.com/chromium/chromium).
Layout follows [perplexityai/rocksdb](https://github.com/perplexityai/rocksdb):
maintained `bcr/overlay`, blank-version module templates, immutable registry staging,
separate development harness and consumer smoke build.

**Linux x86_64 browser build and runtime checks pass.** Native `browser` and
`browser_bundle` targets build Chromium 142.0.7444.59. A relocated bundle passes
`--version` and a real headless HTTP page with external JavaScript/CSS, Unicode,
Intl and layout, using the normal sandbox.
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
- `@chromium//third_party/abseil-cpp:absl`, using shared hardened BCR module update.
- `@chromium//third_party/boringssl:boringssl`, sharing BCR crypto/TLS and original PKI through the build adapter.
- `@chromium//native:base`: full Linux base library and original Rust logger/JSON integration.
- `@chromium//native:base_i18n`: original ICU initialization, locale and encoding support.
- `@chromium//native:grit_resources`: 186 resource actions for strings, WebUI, images, schemas and compressed assets.
- `@chromium//native:crypto`, `@chromium//native:cbor`: complete Linux crypto/NSS utilities and CBOR library.
- `@chromium//native:url_origin`, `@chromium//native:url_scheme_host_port`: complete URL library and production Mojo URL/origin wire types.
- `@chromium//native:mojo_base_types`: complete Mojo base-value schemas and typemaps.
- `@chromium//native:mojo_cpp_bindings`: original Mojo core/embedder, platform, system and C++ bindings runtime.
- `@chromium//native:ipcz`: original core with Chromium base; same transport/portal tests as standalone ipcz.
- `@chromium//native:blink_permission_strings_map`: original generated locale lookup, with pack-content and language-alias tests.
- `@chromium//native:webui_assets`: 1,435 preprocessing, TypeScript, lint, wrapper, bundling and minification targets.

GoogleTest also comes from BCR. Physical forwarding headers preserve Chromium's
Double Conversion, ICU, zlib and GTest production-header include paths. Double
Conversion's BCR version differs from Chromium's 2021 snapshot; it now builds
and runs in the validated browser. Chromium's CityHash has a private
namespace, so it retains upstream's bundled sources.

## Build

Standalone browser staging, from repository root:

```sh
registry=$(mktemp -d)
cp -R compatibility_registry/modules "$registry/modules"
python3 tools/stage_bcr_entry.py --source-registry overlays/abseil-cpp/bcr \
  --target-registry "$registry" --module abseil-cpp --version 20250814.1.chromium142
python3 tools/stage_bcr_entry.py --source-registry overlays/boringssl/bcr \
  --target-registry "$registry" --module boringssl --version 0.20251002.0.chromium142
python3 tools/bundle_chromium_sources.py --target-registry "$registry"
cd overlays/chromium/tests/browser_bcr
bazel build --registry="file://$registry" --registry=https://bcr.bazel.build //:browser
```

The bundler includes the combined pinned source extension and rewrites its
workspace labels into the published module. Existing BCR modules retain their
registry versions; 13 compatibility modules and hardened Abseil/BoringSSL use
separate registry entries. No development dependency overrides are published.
Bazel 9.2.0 is required for this browser package. Standalone full-graph analysis
passes (379,665 configured targets). The combined workspace also passes full
native browser compilation, version and headless HTTP checks. A full standalone
registry build and hosted presubmit remain untested.

The commands below retain the earlier component development harness.

Run commands below from `overlays/chromium`.

Bazel 9.2.0 pinned; published module requires Bazel 8+. Linux x86_64 is the first
validation platform. The development harness uses hermeticbuild LLVM (`llvm@0.8.26`);
published module leaves toolchain selection to its consumer.

```sh
registry=$(mktemp -d)
python3 ../../tools/stage_bcr_entry.py --source-registry ../perfetto/bcr --target-registry "$registry" --module perfetto --version 52.0.chromium142
python3 ../../tools/stage_bcr_entry.py --source-registry ../abseil-cpp/bcr --target-registry "$registry" --module abseil-cpp --version 20250814.1.chromium142
python3 ../../tools/stage_bcr_entry.py --source-registry ../chromium_icu/bcr --target-registry "$registry" --module chromium_icu --version 74.2.chromium142
python3 ../../tools/stage_bcr_entry.py --source-registry ../linux-syscall-support/bcr --target-registry "$registry" --module linux-syscall-support --version 0.0.0-20240201-ed31caa
python3 ../../tools/stage_bcr_entry.py --source-registry ../compact_enc_det/bcr --target-registry "$registry" --module compact_enc_det --version 0.0.0-20190221-ba412ea
python3 ../../tools/stage_bcr_entry.py --source-registry ../ipcz/bcr --target-registry "$registry" --module ipcz --version 0.0.0.chromium142
python3 ../../tools/stage_bcr_entry.py --source-registry ../boringssl/bcr --target-registry "$registry" --module boringssl --version 0.20251002.0.chromium142
python3 ../../tools/stage_bcr_entry.py --source-registry ../nspr/bcr --target-registry "$registry" --module nspr --version 4.29
python3 ../../tools/stage_bcr_entry.py --source-registry ../nss/bcr --target-registry "$registry" --module nss --version 3.61.deb11u3
bazel build --registry="file://$registry" --registry=https://bcr.bazel.build //:foundation
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build //:native_foundation_test
python3 tests/validate_bcr.py
```

Tests cover RFC 4648 vectors, malformed Base64, binary data, UTF-8 supplementary
characters and invalid sequences, CityHash, BCR Double Conversion linkage and
generated boolean, numeric and string flags.

`//:bcr_core_dependencies_test` checks Chromium's original Abseil/BoringSSL
include paths, hash vectors and certificate-verified TLS 1.3 binary transfer.
The Abseil update preserves Chromium's three local patches while sharing BCR's
inline namespace with Protobuf. See [dependency audit](../../docs/dependency-overlays.md).

`//:base_runtime_test` builds all 425 base C++ sources plus seven support sources.
Checks original Rust JSONReader integration, Rust-to-C++ logging, file I/O,
GLib event pumping and a ThreadPool reply. Date/version headers use native
upstream Python generators. Full native browser validation also passes.

`//:base_i18n_test` checks real file-backed ICU startup, French number formatting,
Chromium word boundaries, transliteration, CED detection, encoding conversion and
streaming UTF-8 rejection. `//:grit_resources_test` decodes generated English and
French packs, checks shared ID allocation and gender-pack fallback. 186
native GRIT actions produce 14,913 outputs, retaining locales, genders and image
scales. BCR Brotli builds as a native host tool; `//:grit_binary_resources_test`
checks streams against Chromium's original decoder, compressed shaders/SVG/Lottie,
gzip schemas and PNG packs. `//:webui_test` checks emitted JS, TrustedHTML typing,
type-error rejection and the Downloads page pack. Remaining 9 actions require
generated assets; see [action audit](bcr/overlay/native/grit_targets.json).

## Local registry

```sh
registry=$(mktemp -d)
python3 ../../tools/stage_bcr_entry.py --source-registry bcr \
  --target-registry "$registry" --module chromium --version 142.0.7444.59
python3 ../../tools/stage_bcr_entry.py --source-registry ../perfetto/bcr --target-registry "$registry" --module perfetto --version 52.0.chromium142
python3 ../../tools/stage_bcr_entry.py --source-registry ../abseil-cpp/bcr --target-registry "$registry" --module abseil-cpp --version 20250814.1.chromium142
python3 ../../tools/stage_bcr_entry.py --source-registry ../chromium_icu/bcr --target-registry "$registry" --module chromium_icu --version 74.2.chromium142
python3 ../../tools/stage_bcr_entry.py --source-registry ../linux-syscall-support/bcr --target-registry "$registry" --module linux-syscall-support --version 0.0.0-20240201-ed31caa
python3 ../../tools/stage_bcr_entry.py --source-registry ../compact_enc_det/bcr --target-registry "$registry" --module compact_enc_det --version 0.0.0-20190221-ba412ea
python3 ../../tools/stage_bcr_entry.py --source-registry ../ipcz/bcr --target-registry "$registry" --module ipcz --version 0.0.0.chromium142
python3 ../../tools/stage_bcr_entry.py --source-registry ../boringssl/bcr --target-registry "$registry" --module boringssl --version 0.20251002.0.chromium142
python3 ../../tools/stage_bcr_entry.py --source-registry ../nspr/bcr --target-registry "$registry" --module nspr --version 4.29
python3 ../../tools/stage_bcr_entry.py --source-registry ../nss/bcr --target-registry "$registry" --module nss --version 3.61.deb11u3
cd tests/bcr
bazel run --registry="file://$registry" --registry=https://bcr.bazel.build //:smoke_test
```

Proposed module API, available through a staged registry only:

```starlark
bazel_dep(name = "chromium", version = "142.0.7444.59")
```

Nothing published to BCR. Linux AMD64 browser builds and native rendering smoke
pass in the combined workspace. Other full browser ports remain in progress.
The standalone BCR browser-bundle presubmit has not run. Maintainers recorded
in [bcr/metadata.json](bcr/metadata.json).
See [migration plan](native-browser.md).
Missing dependency overlays and existing BCR alternatives are recorded in the
[dependency audit](../../docs/dependency-overlays.md).

## License

Repository-owned overlay code: MIT. Upstream Chromium and bundled third-party files retain
their own licenses. Registry staging script adapted from perplexityai/rocksdb
(Apache-2.0); see `../../NOTICE` and `../../tools/LICENSE`.

## Perfetto protocol generators

`@chromium//native:perfetto_proto` runs all 87 original browser tracing schema
commands with native BCR protoc and pinned Perfetto compiler plugins. Their
schema sources come from independent `perfetto@52.0.chromium142`; stage that
module in the consumer registry until published. All 969 declared generated files
build. `:perfetto_proto_cpp` compiles 480 generated C++ units; its test compares
original `TraceConfig` wire bytes across ProtoZero, object and Protobuf APIs.
Host plugins retain upstream standalone flags; independent Perfetto base
and ProtoZero variants preserve Chromium runtime flags. Full tracing runtime
integration remains pending.

## Native Rust and CXX

`rules_rs@0.2.1` supplies upstream Rust `nightly/2025-09-25`, matching
standard libraries, patched compilation rules and hermetic bindgen. C++ compilation
and final linking use hermeticbuild LLVM. Compiler downloads and hashes are locked
in `MODULE.bazel.lock`; the custom Chromium compiler archive is no longer used.

`@chromium//native/rust:all_crates` builds the imported crate graph, including CXX,
Chromium's allocator, logger, JSON, font and PNG code. Cargo build scripts execute
as declared Bazel actions. Captured features and per-crate lint policy remain;
`cr_rustc_revision` stamps from the old compiler are removed.

Bindgen keeps Chromium's `bindings.rs` namespace wrapper. Compiler configuration
queries invoke the selected execution toolchain directly, with its complete
sysroot declared as inputs. A small patched-rules_rust fix sends MSVC linker
arguments to LLVM's `lld-link`, preserving SDK paths and its VFS case overlay.

Consumers that need direct Rust rule loads can expose the shared repository:

```starlark
bazel_dep(name = "rules_rs", version = "0.2.1")
rules_rust = use_extension("@rules_rs//rs:rules_rust.bzl", "rules_rust")
use_repo(rules_rust, "rules_rust")
```

Select the nightly channel in `.bazelrc`:

```bazelrc
build --@rules_rust//rust/toolchain/channel=nightly
```

CI cross-compiles standard-library probes for Linux amd64/arm64, Darwin arm64
and Windows MSVC amd64/arm64, then runs the native Linux probe. The font-outline
and PNG runtime test also passes with this compiler. These probes do not establish
full browser ports; their platform-specific graphs remain unfinished.

Darwin arm64 and Windows MSVC amd64/arm64 cross-link base, IPC, TCP sockets,
V8 and Skia rendering probes. V8 bundles its target snapshot and ICU data.
Rendering smoke draws shapes, encodes PNG with Rust, decodes it and checks every
pixel. Native runners exercise these artifacts and upload the PNG. These are
component checks; full browser ports remain in progress.

Regenerate platform profiles without changing the Linux overlay:

```sh
python3 overlays/chromium/tools/import_platform_base.py \
  --variant darwin_arm64 --source-root /path/to/chromium --desktop
```

Use `windows_amd64` or `windows_arm64` for Windows. `--desktop` includes V8,
geometry, fonts, codecs, Dawn, Skia, paint and gfx. Darwin retains Objective-C++
ARC flags and generates Crashpad interfaces with pinned Clang and MIG tools.
Windows uses MSVC, `llvm-ml` for MASM and `llvm-nasm` for NASM.

ARM64 host generators reuse native graphics libraries only when captured sources,
compiler/linker flags, outputs and dependencies match the Linux AMD64 graph.
Shared libraries keep their original GN runtime paths. V8 and Blink retain their
target-specific layouts.
For isolated import stages, pass `--native-overlay /path/to/native/bcr/overlay`
to `import_cpp_layer.py` so provider names come from the native profile.

Regenerate the imported crate graph from the pinned checkout:

```sh
python3 overlays/chromium/tools/import_rust_crates.py \
  overlays/chromium/native/linux_x64.json.gz --source-root /path/to/chromium
buildifier -r overlays/chromium
```

## Browser tracing runtime

`@chromium//third_party/perfetto:libperfetto` aliases the native
`@chromium//native:perfetto_runtime` library. It compiles 159 original SDK sources
and generated IPC code, reusing previously ported protocols. Five upstream Python
actions generate table and descriptor headers. Source and compiler metadata live
in the independently staged Perfetto overlay; generated browser protocols remain
owned here.

The runtime preserves Chromium DCHECKs and supports its original Perfetto header
paths. BCR JsonCpp and zlib are checked through JSON roundtrip/fatal-type handling
and compression/CRC behavior. Live tracing test exercises real in-process
recording and decodes the expected event and argument.

```sh
python3 overlays/chromium/tools/import_perfetto_runtime.py \
  overlays/chromium/native/linux_x64.json.gz /path/to/pinned/perfetto
buildifier -r overlays/chromium
```

Full trace processor remains outside the captured browser profile. Complete
base and browser integration now build; headless HTTP checks pass.
