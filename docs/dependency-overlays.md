# Dependency overlay audit

Current build uses one root workspace and `build/dependencies.bzl`. Existing
overlay directories remain source/rule storage. Separate BCR publication and
registry staging are outside the main build path. New dependency ports stay
inside Chromium first; compatibility findings below still apply.

Checked 2026-11-03 against the complete BCR module directory
([registry tree](https://api.github.com/repos/bazelbuild/bazel-central-registry/git/trees/b275823006bd7e75f72f41f7bfcd31609076da9e),
1,394 entries). Names and feature coverage below are a first pass, not a complete
Chromium dependency inventory.

## New overlays

No matching BCR modules found for these seven dependencies. Prioritize V8,
Skia and ANGLE, then the remaining browser features. Each overlay needs a
native Bazel implementation; directory scaffolding alone does not supply one.

- [V8](../overlays/v8): native engine graph, Torque and snapshot actions ported
  from upstream Bazel. ICU and no-ICU variants pass; browser integration pending.
- [Skia](../overlays/skia): native raster core/path operations pass consumer
  tests. GPU backends, codecs, fonts and Chromium configuration pending.
- [ANGLE](../overlays/angle): native WebGL shader compiler passes ESSL/GLSL
  consumer checks. EGL/GLES rendering and Vulkan/SPIR-V remain pending.
- [Dawn](../overlays/dawn): native API/Tint/backends and software-Vulkan
  compute/raster pass in the combined workspace; standalone release pending.
- [WebRTC](../overlays/webrtc): real-time audio/video and data
  channels; align Chromium integration flags and codec dependencies.
- [PDFium](../overlays/pdfium): PDF viewer; align font, image and
  JavaScript dependencies with Chromium's integration.
- [SwiftShader](../overlays/swiftshader): native Subzero driver and software-Vulkan
  compute/raster pass; standalone registry entry remains planned.

Initial pins come from Chromium 142.0.7444.59's
[DEPS](https://github.com/chromium/chromium/blob/4b8153ab58d3c3f4c9f7e4baad9616ecf80db5fa/DEPS):

```text
v8          bb294624702efbb17691b642333f06bf5108e600
skia        f4ed99d2443962782cf5f8b4dd27179f131e7cbe
angle       e5b338502c7c65bd38d4695bc557938ca4cc3aa7
dawn        cee9cb0d67e749bf42f5e90cb3b8a6f525dbb920
webrtc      29d6eabaf0b5c1a62af6e7fd03adebf5e1a446e8
pdfium      e95c6ead2f97716c98526ec42d5fd9ebb50e6e23
swiftshader 5f1c459a11bb4899301e89609cbf7547f9f31e20
```

## Reuse existing BCR entries

The audited registry contains Abseil (`abseil-cpp`), BoringSSL (`boringssl`),
ICU (`icu`), zlib, Brotli, libpng, libjpeg-turbo (`libjpeg_turbo`), FreeType,
HarfBuzz, SQLite (`sqlite3`), Protobuf, RE2, Snappy, Zstd, libevent, FFmpeg,
libvpx, Opus, libyuv and AV1 (`aom`). Double Conversion and GoogleTest are
already used by this repository's foundation build.

Check each entry's version, Chromium patches, exported headers and configuration
before adopting it. FFmpeg and codec overlays are not automatically compatible
with Chromium's forks. Prefer extending an existing overlay over creating a
duplicate for the same library.

## Keep inside Chromium overlay

Blink, Mojo, GRIT and PartitionAlloc sources are in the Chromium checkout.
They need native targets and generator actions in `overlays/chromium`; separate
modules are not required for the initial browser build.

## Additional dependencies found while building V8

- [Dragonbox](../overlays/dragonbox): absent from the same audited BCR tree.
  Added native header-only overlay at V8's exact 1.1.3 source pin.
- [FP16](../overlays/fp16): already in BCR. Its BUILD uses native `cc_library`,
  removed in Bazel 9. Prepared an update under the existing module name,
  preserving its source checksum and compatibility level.
- FastFloat and Highway already have BCR revisions with explicit C++ rule
  loads. Reuse `fast_float@8.2.4` and `highway@1.4.0.bcr.1`.
- simdutf already exists as `simdutf@7.7.0`; reuse its single-header library.

V8's consumer check exercises adopted libraries through engine execution.
Full Chromium compatibility remains pending. All harnesses use hermeticbuild
LLVM `llvm@0.8.26`; published library modules do not select a compiler.

## Native validation

Linux x86_64, Bazel 9.2.0, hermeticbuild LLVM `llvm@0.8.26`:

- Chromium foundation test and staged BCR consumer pass. Native allocator core
  passes realloc, zero-fill, alignment and fatal cookie-corruption checks.
  Native generator ports cover 118 buildflag actions and 3,457 metadata writes.
  Malloc/new shim consumer verifies allocation ownership and raw-pointer linkage.
  Full Mojo generator closure builds natively; protocol wire-contract test passes.
- V8 `noicu/v8`, Torque, inspector bindings, snapshots and `noicu/d8` build.
  Embedding test passes JavaScript, decimal conversion, BigInt, half floats,
  Unicode/Base64, actual WebAssembly execution and Promise microtasks.
  `d8` executes JavaScript and reports `14.2.231.14`.
  ICU variant additionally passes locale formatting, NFC and patched word breaks.
- Skia's staged consumer passes raster pixel and path-intersection checks.
- ANGLE's staged consumer passes ESSL/GLSL translation, invalid shader
  rejection and archive-metadata checks.

These are component milestones. No `chrome` target or full browser build yet.

## Full-browser graph audit

`tools/read_deps.py` resolves the pinned DEPS file's 419 entries through a
restricted AST reader. Conditions remain data; upstream Python never executes.
Use `--output` to capture the inventory when preparing a source checkout.

Chromium's ICU pin `1b2e3e8a421efae36141a7b932b41e315b089af8` is a patched
74.2 tree, with checked-in platform data. BCR currently starts at 76.1.
Name presence alone does not prove this replacement is compatible. The Chromium
fork carries locale and break-iterator changes. BCR HarfBuzz already depends on
ICU 76.1, so a 74.2 dependency under the same module name would be upgraded by
Bazel version resolution. A separate `chromium_icu` fork module is needed to
preserve Chromium's baseline without overriding other consumers' stock ICU.

Pinned GN `81b24e01531ecf0eff12ec9359a555ec3944ec4e` is being used only as a
maintainer tool to extract the complete `//chrome:chrome` target graph. Captured
16,619 targets and 4,753 runtime files in `overlays/chromium/native`. Native
Bazel builds must not depend on or execute GN/Ninja. This graph audit supplements
the component overlays; it does not establish a browser build.

## Chromium ICU fork

`chromium_icu@74.2.chromium142` preserves Chromium's exact ICU revision and data.
Embedded and file-data consumers pass with hermetic LLVM. Tests cover version,
NFC, French number formatting and Chromium's patched `example.com` word breaks.
Source uses maintainer's GitHub mirror at identical commit/tree with fixed SRI;
GoogleSource's generated tar metadata produced different archive checksums.
Stage Chromium ICU before V8, independently from other modules.

## BCR Protobuf compatibility probe

Reuses `protobuf@33.4`, required by Bazel 9.2's built-in module, with matching
compiler/runtime. Chromium schemas originate from its 32.0 baseline. Scoped
native dependencies preserve Chromium's abort-on-bounds-violation and RTTI
configuration. Variations protocol test passes exact wire, unknown-field,
required-field, UTF-8-policy and fatal bounds checks. This does not establish
compatibility for every Chromium Protobuf consumer; full integration continues.

## Perfetto host tools

Independent `perfetto@52.0.chromium142` uses Chromium's exact upstream commit
`d5bbee7afdf259af4212929ccbff467dd5349953`. Stable GitHub archive matches all
10,649 files in the DEPS checkout. Native ProtoZero, C++ object, and IPC compiler
plugins build with hermetic LLVM and BCR Protobuf 33.4. Generated ProtoZero/object
serialization passes fixed-wire roundtrip validation. Chromium imports all 87
Perfetto schema actions, producing 969 files; 480 generated C++ units compile.
Original TraceConfig wire compatibility test covers ProtoZero/object/Protobuf.
Independent Chromium-configured base and ProtoZero variants pass generated wire
tests. Browser tracing, service, IPC, JSON export and minimal storage now compile
from 159 additional C++ sources plus generated IPC. Five native Python actions
produce table/descriptor headers. Live in-process recording and decoding passes
with DCHECKs enabled. BCR JsonCpp 1.9.6.bcr.2 preserves scoped exception/null-ref
settings; BCR zlib 1.3.1.bcr.9 passes binary compression and CRC validation.
Full trace processor and browser integration remain pending. BCR had no Perfetto
module during this audit.

## Rust prerequisites

Reuses BCR `rules_rust@0.75.0` and `rules_rust_bindgen@0.75.0`. Chromium's pinned
Rust 1.92.0-dev toolchain preserves unstable allocator hooks and ships bindgen
with libclang 22. C++ compiler/linker remains hermeticbuild LLVM. Toolchain archive
uses original DEPS SHA-256 and immutable GCS generation.

CXX has no BCR `cxx` module during this audit. Chromium's vendored 1.0.185
compiler/runtime remain matched, including its patched header layout. Thirty-seven
native Rust targets and five build scripts compile from original tracked sources.
Real CXX and allocator tests cover cross-language ownership, Chromium crate
imports, PartitionAlloc routing and fatal allocation behavior. Chromium's pinned
serde/lenient JSON crates and original CXX wrapper also compile. Parsing checks
cover comments, trailing commas, invalid Unicode, strict rejection, trailing
input and numeric round trips. Cargo build scripts supply generated serde source
through native `OUT_DIR` providers. Original Rust logger and its generated CXX
and bindgen dependencies now compile as part of the full native base library;
runtime test captures an actual Rust log through C++ logging.

## Abseil and BoringSSL

`abseil-cpp@20250814.1.chromium142` updates the existing BCR module with
Chromium's hardening, annotation isolation and generic stacktrace initialization
patches. Keeps BCR's inline namespace so Protobuf and Chromium resolve one ABI.
The module's `absl/chromium:absl` facade preserves Chromium's component list
without widening upstream internal visibility. Independent release-mode bounds,
annotation, container and stacktrace checks pass. Shared-module Protobuf wire
and Perfetto live-tracing regressions also pass.

Chromium's original include paths use physical forwarding headers to the shared
module. This also replaces vendored headers that would otherwise win quoted
include lookup and mix implementations. BoringSSL uses the existing BCR `0.20251002.0` source snapshot through
`boringssl@0.20251002.0.chromium142`, exposing Chromium's PKI bindings. Native consumer
passes SHA-256/SHA-1/MD5 vectors, entropy generation and verified TLS 1.3 binary
transfer. Full browser compatibility remains pending.

## Linux Syscall Support

Independent `linux-syscall-support@0.0.0-20240201-ed31caa` preserves Chromium's
exact `ed31caa60f20a4f6569883b2d752ef7522de51e0` header. Registry lookups for
`lss`, `linux-syscall-support` and `linux_syscall_support` returned 404 during
this audit. Native consumer validates process/thread IDs, `/proc/self/stat`
reads and errno behavior with hermetic LLVM. All 22 mirror archive files match
the exact [upstream revision](https://chromium.googlesource.com/linux-syscall-support/+/ed31caa60f20a4f6569883b2d752ef7522de51e0).
GoogleSource tar metadata changed between downloads; fixed-SRI source uses the
matching CitizenFX GitHub mirror.

## Full Linux base library

`@chromium//native:base` compiles the exact `//base:base` source list: 425 C++
sources plus seven sources for base switches, DWARF, symbolization, CityHash
v1.0.3 and XDG directories. Keeps original release/hardening settings and
DCHECKs. Native upstream Python generates build date and version headers;
original Rust logger uses native CXX and bindgen. Browser tracing schemas add
two native protocol actions to the existing 87 Perfetto actions.

Reuses [BCR GLib 2.82.2.bcr.11](https://registry.bazel.build/modules/glib/2.82.2.bcr.11)
for event pumping, GModule and GObject. Physical forwarding headers preserve
Chromium's ICU, zlib, Double Conversion, GTest production and LSS include paths.
Production uses only GoogleTest's header target, without linking its test runner.
Runtime integration covers original C++ JSONReader/Rust wrapper, Rust logging,
binary file I/O, GLib event loop and ThreadPool reply. Full browser integration
remains pending.

## Base internationalization and CED

`base_i18n` ports all 20 original C++ sources. Preserves file-backed ICU data and
the original transliterator buildflag. Runtime checks cover ICU file mapping,
French formatting, Chromium word breaks, case mapping, transliteration, encoding
conversion and streaming UTF-8 boundaries/errors.

Independent `compact_enc_det@0.0.0-20190221-ba412ea` uses the exact DEPS revision
`ba412eaaacd3186085babcd901679a48863c7dd5`. No BCR module under `ced`,
`compact_enc_det` or `compact-enc-det` during lookup. Four original C++ sources
retain `HTML5_MODE`, including unsupported-encoding fallback. Static linkage
preserves Chromium's hidden-symbol configuration. Independent fixtures cover
UTF-8, Shift-JIS, ISO-2022-JP and HTML5 UTF-16 behavior.

## GRIT resources

186 native GRIT actions allocate shared IDs and generate 14,913 outputs.
Declared locales, genders and image scales remain.
Maintainer discovery uses original GRIT input analysis plus recursive XML
fragment closure; conditional GRDP files are declared even when their output
branch is inactive. Original expected-output assertions remain enabled.
Resource tests decode English/French packs, validate nonoverlapping ID ranges
and apply gender override fallback. Tracing descriptors and Mojo bindings reuse
their native producers. Remaining 9 actions are reported with unresolved
producer labels in `native/grit_targets.json`: five code-cache packs, DevTools,
Catapult tracing and credits. Browser resource assembly
remains pending.

Native WebUI preprocessing, TypeScript, ESLint, HTML/CSS wrappers, Rollup and
Terser supply generated GRDs and assets. Chromium's complete patched Node source
archive is pinned directly from DEPS. Downloads-page tests decode the actual
pack, check its module reference, compare packed JS with minified output and
validate module syntax. Compiler tests accept TrustedHTML and reject invalid
types without emitting JS. The original TS Protobuf plugin now generates and
compiles traces-internals schemas. Its JS codec matches golden wire bytes used
by all three native C++ Perfetto APIs and rejects truncated messages.

Blink permission-element strings now use their original Python generator and
compiled C++ lookup. Native tests check French text against both the combined
pack and regular locale pack, language aliases, and missing lookup results.

Existing [BCR Brotli 1.2.0.bcr.3](https://registry.bazel.build/modules/brotli/1.2.0.bcr.3)
supplies the native host CLI. Compatibility probe compiles Chromium's original
decoder from its bundled sources, decodes actual SVG/shader/Lottie resources and
rejects truncated streams. Binary pack tests also check gzip descriptor bytes,
uncompressed PNG bytes and image resources at three scales. This validates the
resource-compression use; other browser Brotli consumers remain to be ported.

## Mojo runtime and ipcz

Native Mojo generators, Linux core, embedding and C++ bindings now build.
The [BCR catalog snapshot](https://api.github.com/repos/bazelbuild/bazel-central-registry/git/trees/f7596b9dac1e438ebbc72230ade86a4d26bd3073)
contains 1,394 module entries and no `ipcz` module. BCR `rules_mojo` targets the
[Modular Mojo language](https://github.com/modular/rules_mojo), rather than
Chromium IPC.

Independent `ipcz@0.0.0.chromium142` now builds the canonical source from
[`third_party/ipcz`](https://github.com/chromium/chromium/blob/142.0.7444.59/third_party/ipcz/README.chromium).
It reuses Chromium's immutable archive and original platform headers. Native
source inventory includes 36 core C++ files; standalone support adds two files.
The library macro accepts the caller's base target for Chromium mode, avoiding
an ipcz/Chromium module cycle. Standalone mode selects `IPCZ_STANDALONE` and
stock BCR Abseil. Chromium mode uses native base and its shared hardened Abseil.
Original compiler optimization, stack protection and automatic-variable
initialization flags remain.

Both implementations run the same real synchronous-driver test: broker/client
connection, 65 KB binary transfer, receive-capacity rejection without consuming
data, portal transfer, communication through the transferred portal, peer
closure and invalid-input rejection. These remain reference-driver checks.

Actual Mojo core, ipcz driver, embedding, platform/system and C++ bindings now
compile separately with original flags. A production InterfaceProvider schema
exercises the native generated C++ path. The 128-source closure uses original Unix
address helpers without claiming full net/crypto libraries. Runtime tests use
real parent/child processes, invitations, binary and shared-memory transfer,
generated RPC and malformed-message rejection. This validates Mojo integration;
remaining browser service consumers and browser assembly still need ports.

The complete 26-source URL library and original URL/origin Mojo traits now compile
with Chromium ICU. Complete Mojo base-type schemas and typemaps add 107 C++
sources. URL runtime checks cover IDNA, canonicalization, origin identity, opaque
nonce preservation and rejection of malformed wire payloads. Full net and
network-service implementations remain pending.

## NSS and NSPR prerequisites

Chromium 142's captured Linux crypto target links NSS and NSPR. Its pinned
Bullseye sysroot package controls identify NSS `2:3.61-1+deb11u3` and NSPR
`2:4.29-1`. Neither `nss` nor `nspr`
has a BCR module metadata entry (checked 2026-11-03).

`nspr@4.29` now builds the original Linux pthread runtime, x86_64 atomic assembly,
PLC and PLDS through native Bazel actions: 73 C sources plus one assembly source.
Its integration test covers dynamic module loading, threaded TCP transfer,
timeout/EOF, file mapping, sparse files above 4 GiB, error translation, Base64,
arena allocation and hash tables. Published module leaves compiler choice to
consumers; tests register hermeticbuild LLVM. No NSPR source patch is applied.
Native NSS and Chromium crypto integration follow below; full net remains pending.

The NSS source port preserves Debian's `3.61-1+deb11u3` patch series,
including CVE-2021-43527 signature-size checks, CVE-2022-22747 missing signed-data
checks and CVE-2023-0767 PKCS#12 handling. Vanilla Mozilla 3.61 omits those fixes.
The exact [Debian source patch archive](https://archive.debian.org/debian/pool/main/n/nss/nss_3.61-1+deb11u3.debian.tar.xz)
has SHA-256 `3ea623845a92df91fa2065b5878aadf8bc5ff8ef1e51cecc1ad8196f300778aa`.
NSPR's matching Debian source package has no downstream patch series.

## Native NSS

`nss@3.61.deb11u3` now builds the Linux shared-library graph with all seven Debian
patches. Native actions generate certificate data, ELF version scripts and
integrity files using original `shlibsign`. FIPS, legacy DBM, libpkix and optimized
crypto remain enabled. Native NSPR supplies shared libraries so NSS modules use
one runtime instance.

Existing BCR SQLite `3.51.1.bcr.1`, zlib and Perl rules are reused. SQLite
compatibility checks create, sign with and reopen persistent SQL keys; legacy DBM
keys pass the same checks. Runtime tests cover SHA-256, AES-GCM golden bytes and
tag rejection, RSA signatures and modified-data rejection. FIPS tests enforce PIN
policy and raw-key import rejection before generated-key crypto. Both modes reject
modified libraries and checksum signatures through actual freebl verification.

A small source patch canonicalizes the loaded module path before checksum lookup.
Bazel places each DSO behind a distinct `_solib` symlink; integrity files belong
beside the actual module. Original verifier still checks module bytes and signature.
Published C++ dependencies carry runtime modules and integrity files automatically.
Chromium crypto now uses these modules; full networking remains pending.

## Chromium crypto and PKI

Complete Linux crypto imports 29 original C++ sources; CBOR adds all five source
files. Per-target compiler flags and defines come from the GN snapshot. NSS uses
the combined source repository and signed runtime files.

Chromium's original BoringSSL GN aggregate includes PKI. The selected BCR snapshot
keeps `:pki` private; a build-only adapter exposes its existing library and headers.
The source archive and crypto/SSL implementation stay shared with BCR. Original
upstream PKI suite passes 1,280 tests through hermetic LLVM. Chromium adapters now
forward 137 BoringSSL headers, including 38 PKI paths.

Runtime checks exercise Chromium's SHA-256, RFC 5869 HKDF, AES-GCM golden bytes
and authentication failures, PKCS#8 parsing, BoringSSL/NSS key and signature
interoperability, PEM file helpers, COSE P-256 and malformed CBOR rejection.
Full net and browser integration remain pending.

Networking audit (2026-11-04): BCR module metadata is absent for `quiche` and
`google_quiche`. Chromium DEPS pins Google's QUICHE to
`c0df0d316bd7e4ddf44e5ba094b5c5b061d94b0c`. The captured Linux target contains
313 C++ sources and depends on native base/URL, shared Abseil/BoringSSL, Protobuf,
zlib, QUIC protocol generation and URI templates. All 313 sources, the URI
expander and three generated protocol sources now compile in the combined root
workspace. The original Chromium platform overrides use native base/URL; no
standalone GoogleURL dependency is needed.

`//:quiche_runtime_test` passes RFC 7541 HPACK Huffman and dynamic-table vectors,
RFC 9458 OHTTP decryption, a 65,537-byte binary request/response, ciphertext
mutation/truncation rejection, Protobuf golden bytes and malformed-message
rejection, RFC 6570 URL expansion and non-ASCII decode rejection. Protobuf
consumers omit LLVM's `-fcomplete-member-pointers` diagnostic because Protobuf
33's constexpr metadata forward-declares its member-pointer base. Bounds-abort
and no-RTTI configuration remain enabled. Full net and browser integration are
still pending.


## Combined networking and SQL

All 565 source files in the Linux `//net:net` target now compile, including both
Mozilla NSS `.cpp` implementations. The complete new closure imports 685 C/C++
units into 41 original libraries/groups/host tools. Seventeen native Python/tool
actions generate protocol schemas, version metadata, SQL names, DAFSA tables,
certificate roots and HSTS preloads. Existing native GRIT/buildflags and QUICHE
remain shared. Source inventories match captured GN target sources.

Root dependency resolution shares BCR RE2 `2025-08-12.bcr.1`, Zstd
`1.5.7.bcr.1`, Brotli `1.2.0.bcr.3` and simdutf `7.7.0`. Forwarding headers retain
original Chromium include paths. Link inputs use native GLib/GIO and NSS
providers; captured no-exec-stack, RELRO, immediate binding and other linker
options remain enabled. LLVM supplies compiler/runtime paths.

Chromium's SQLite 3.50.4 commit is
`7d348fc79216a09b864ff881d8561a6222301666`. Its amalgamation, generated API renaming,
ICU support and original configuration compile inside Chromium. Symbols stay
under `chrome_`; NSS uses BCR SQLite 3.51.1. Runtime tests load both in one process
and exercise transactions, binary values, Unicode case conversion, duplicate-key
rejection, DQS=0 and API armor. No new standalone SQLite overlay.

Kerberos compiles with original GSSAPI ABI headers from the SHA-256-pinned
Bullseye SDK. Only the two GSSAPI headers enter compilation; libc and C++ runtime
come from hermeticbuild LLVM. Original runtime platform-library loading remains.

`//:network_runtime_test` passes real loopback HTTP and HTTPS, TLS 1.3, rejection
of an untrusted CA, acceptance through an explicit test root, binary transfers,
Brotli/Zstd streams, corrupt-Zstd and conflicting-header rejection. Truncated
Zstd EOF retains Chromium's original successful-read/error-histogram behavior.
Full browser executable and renderer/service integration remain pending.


## Combined geometry

Geometry/range and their Mojo bindings compile inside the root workspace:
47 original C++ units across 11 targets. Existing Mojo actions supply generated
schemas. The geometry/Skia math bridge uses the full captured Chromium Skia provider,
including its original public header configuration and link dependencies.

`//:geometry_runtime_test` covers clipping, half-open bounds, enclosing rounding,
transform inversion, singular matrices, Skia matrix conversion, rounded corners,
reversed/invalid ranges, Mojo round trips, truncated messages and negative wire
sizes. No production geometry or serialization checks were changed.


## Renderer prerequisites: Fontations, PNG and Dawn API

The combined Chromium Rust graph now includes all pinned Fontations and PNG
prerequisites: 52 crate targets and six native build scripts overall. Original
features, Chromium patches and Rust debug assertions remain enabled. Runtime
coverage loads Chromium's Ahem font, maps and draws its glyph outline, decodes
known PNG pixels, and rejects invalid signatures, truncated data and CRC errors.

Dawn's original API/common/dispatch closure now builds inside Chromium: eight
targets, 20 C++ units and ten native Python generators. Source archive commit
`cee9cb0d67e749bf42f5e90cb3b8a6f525dbb920` has SHA-256
`604b16af14b41e2485df4d9e65f749d649e5c25729a1de43569b41e63249a16e`.
Generator sources match the captured checkout. Native write actions retain
original expected-output lists and the pinned version hook input. Existing
Jinja/MarkupSafe inputs and shared Abseil/PartitionAlloc remain in use.

Dawn has no BCR entry at this audit. BCR Vulkan-Headers 1.4.349 provides the header
library; GPU backend consumers still need compatibility checks. Dawn retains
`DAWN_ENABLE_ASSERTS` and `DAWN_ABORT_ON_ASSERT`; a child-process test verifies
SIGABRT. Dispatch tests cover C++ handle ownership and thread-local override
isolation. Dawn software-Vulkan compute/raster execution now passes. Full captured Tint and
Skia compile; Skia GPU integration remains unverified.


## Combined Linux font stack

Seven original targets now compile 171 C/C++ units for FreeType, HarfBuzz,
Fontconfig, PNG and XML. Native rules split C and C++ compilation flags while
retaining source lists, custom headers, original defines and linker options.

Exact font sources:

- FreeType `d3668e00da732654b50e4e81f982544ed6e26390` (2.13.3 plus updates).
- HarfBuzz `7d936359a27abb2d7cb14ecc102463bb15c11843` (11.4.4 plus updates).
- Fontconfig `f0ed9c3f43161d3555f6f7a5234b22fe7ca60727` (2.17.1).

BCR has FreeType builds but not Chromium's exact revision/configuration;
HarfBuzz's captured revision/configuration also differs. BCR Fontconfig 2.16.0
lacks the captured Fontations integration. Chromium's PNG 1.6.43 has custom
feature/chunk limits; XML 2.14.2 carries local patches including `_xmlAttr.extra`.
Those checked-in sources/configurations remain intact. BCR libuuid
`2.41.2.bcr.1` provides the UUID dependency and passes native generation/parsing.

Original Fontconfig C/Rust integration now uses native bindgen with both original
allowlists and Chromium's `bindings.rs` wrapper. The full Rust group grows to
55 targets and seven build scripts. `BINDGEN_IGNORE_VISIBILITY`, `FC_NO_MT` and
`FLEXIBLE_ARRAY_MEMBER` remain parser-only flags. Compiler-command audit confirms
none appear in any of the 29 production Fontconfig C actions; Fontations stays
enabled.

`//:fonts_runtime_test` rasterizes Ahem glyphs, checks LTR/RTL advances and ICU
Unicode properties, parses family aliases through XML and matches the real font
through both FreeType and Fontations. Both reject malformed font input. PNG
checks cover exact pixels, valid-CRC oversized dimensions and compressed-text
expansion limits. XML tests cover Unicode entities and malformed nesting. Browser integration remains pending.


## Combined JPEG, WebP and Wuffs

All 25 captured codec targets now build natively: 213 C/C++ units and 27 JPEG
SIMD assembly objects. BCR NASM `2.16.03.bcr.4` supplies the host assembler;
`rules_cc_autoconf` 0.33.1 supplies native configuration probes compatible with
Bazel 9 execution groups. Original assembly arguments retain ELF/PIC and
`--reproducible`. No external build backend.

JPEG source commit `e14cbfaa85529d47f9f55b0f104a579c1061f9ad` retains the
Chromium `chromium_` symbol mangling, patched configurations and 8/12/16-bit
implementations. WebP source `b0e8039062eedbcb20ebb1bad62bfeaee2b94ec6`
contains changes after the BCR 1.6.0 release, including DSP initialization
changes. Wuffs source `e3f919ccfe3ef542cfc983a82146070258fb57f8` retains the
original GIF/LZW/base modules; no Wuffs BCR entry exists at this audit.

`//:codecs_runtime_test` covers 8-bit JPEG color conversion, exact 12/16-bit
lossless samples, WebP alpha pixels, undersized-output/truncated-input rejection,
animated-container mux/demux/frame pixels and durations, and Wuffs GIF pixels
plus truncated-header rejection. Original Chromium WebP targets expose demuxing
and frame decoding; the separate upstream AnimDecoder helper is not included.
Browser integration remains pending.

## Combined Chromium Skia

The full captured graph compiles 1,138 C++ units across 17 targets, retaining
Ganesh, Graphite, GL/Vulkan/Dawn integration, SkSL, PDF and Skottie. Native
Python and CXX actions generate GPU workarounds and font/PNG bridges. Original
Fontations and PNG Rust libraries compile with their captured configuration.
BCR libexpat 2.7.1.bcr.1 supplies Expat. The source projection shares the pinned
Skia archive and exposes original paths without upstream package boundaries.
Public flags come from the captured `skia_config` consumer, preserving Chromium
assertions, reference counting, pixel order and class layouts across consumers.
GPU execution and browser integration remain unverified.

`//:skia_runtime_test` verifies Fontations glyph advances/outlines, raster text
pixels, Rust PNG encoding with both libpng and Rust decoding, truncated-input
rejection, PDF font embedding and fatal Chromium Skia assertions. Geometry also
passes against this full provider. GPU execution remains unverified.

## Compositor paint

`@chromium//native:paint` retains the complete captured `//cc/paint:paint`
closure: 31 targets, 213 C++ units and two Crashpad assembly sources. It shares
existing Skia, networking, Mojo and geometry implementations. New sources cover
compositor helpers/debugging, animation, color management, HDR/Skia Mojo traits,
Linux UI/display types, crash keys and Crashpad client/util support. Crashpad
uses Chromium base through its original adapter; no mini_chromium substitute.
Original assembler flags and the ELF Crashpad info note remain intact.

`//:paint_runtime_test` checks every raster pixel from clipped/transformed nested
records, serializes through the production renderer-to-raster format and checks
decoded pixels. Truncated/invalid operations and insufficient output capacity
must fail. Color checks cover sRGB/Skia conversion and HDR classification; crash
keys exercise real Crashpad annotation registration, lookup and clearing.
Crash handler startup, GPU execution and browser assembly remain unverified.

## Linux graphics consumers

`@chromium//native:gfx` now builds the full captured `//ui/gfx:gfx` closure.
Thirteen additional targets retain 90 C/C++ units plus the original Python DRM
format-table action. Dependencies reuse the existing paint, geometry, font,
codec, Mojo and Skia providers. Added code includes image representations,
screenshot codecs, color utilities, native buffers/fences, resource packs and
Google zlib compression helpers. C and C++ keep separate captured compiler flags.

DRM and sync have no BCR modules at this audit. Source repositories use exact
Chromium DEPS pins: libdrm `ad78bb591d02162d3b90890aa4d0a238b2a37cde` and
libsync `f4f4387b6bf2387efbcfd1453af4892e8982faf6`. Declared header providers
preserve original include paths; native Python generates the DRM modifier table.

`//:gfx_runtime_test` checks PNG alpha pixels, image-representation conversion,
JPEG/WebP screenshot pixels, ICC profile round trips and malformed inputs. It
writes and loads binary resource packs with aliases, including gzip-compressed
packs, and rejects truncated headers. Linux checks cover fence-handle ownership,
sync polling/invalid descriptors, DRM format lookup and invalid-device handling.
Pipe descriptors exercise ownership/polling without requiring a GPU. GPU-backed
fences, actual display operation and browser assembly remain unverified.

## Tint shader translation

`@chromium//native:tint` builds the complete captured Tint API closure from the
same pinned Dawn revision: 72 targets and 433 C++ units. Original WGSL reader
and WGSL/SPIR-V/GLSL/HLSL/MSL writers remain enabled; the SPIR-V reader retains
its captured disabled setting. Public feature flags match library compilation.
Source projection shares Dawn's archive and removes upstream Bazel packages.

BCR `spirv_headers@1.4.341.0` supplies C/C++ headers through one adapter;
`spirv_tools@2026.1` supplies native validation/optimization. Its native build
requires `rules_python@1.9.0`, now selected by the combined root module. No
Tint source patches, prebuilt shader tools or foreign build actions are used.

`//:tint_runtime_test` parses/validates WGSL, prints and reparses it, and emits a
storage-buffer compute shader through every captured output backend. Independent
SPIR-V validation/optimization and ANGLE GLSL compilation check generated output.
Bounds clamping survives optimization. Tests also
reject WGSL syntax/type errors and corrupt SPIR-V. HLSL/MSL emission is checked;
platform compiler execution remains unverified. WGSL/SPIR-V execution is now
covered by the SwiftShader tests below.

## Dawn native library

`@chromium//native:dawn_native_library` compiles all 190 additional C++ units
across eight captured targets, including OpenGL, desktop GL, GLES, Vulkan and the
original null backend. Four native Python actions generate loader/validation/
feature/structure sources from original templates and expected-output inventories.
BCR Vulkan utility headers 1.4.349 join matching Vulkan headers and SPIR-V tools.

Nested Khronos sources use Dawn's exact DEPS pins: EGL-Registry
`7dea2ed79187cd13f76183c4b9100159b9e3e071` and OpenGL-Registry
`5bae8738b23d06968e7c3a41308568120943ae77`. Their XML inputs and headers are
separate pinned source repositories; neither has a BCR entry at this audit.

`capture_dawn_runtime_edges.py` evaluates original GN `data_deps`, restoring the
maintainer source after success or failure. Source/graph hashes bind the committed
`native/dawn_runtime_edges.json` to this capture. Import rejects mismatched inputs.
The generated `dawn_native_runtime_requirements` manifest retains Vulkan loader,
SwiftShader and validation library/JSON dependencies. All four runtime dependencies now build through `dawn_native_runtime`. The manifest
is not a complete browser runtime bundle.

`//:dawn_native_runtime_test` uses the captured null backend to check real native
instance/device creation, zeroed buffer allocation, mapped-byte preservation,
asynchronous mapping, compute pipeline/command submission and scoped validation
errors for invalid buffer usage and WGSL types. Software-Vulkan execution now passes through SwiftShader; final browser runtime
assembly remains unfinished. Captured backend, assertion and validation flags stay
unchanged; Vulkan/SwiftShader/validation-layer flags remain enabled.

## Vulkan runtime artifacts

`@chromium//native:libvulkan.so.1` builds all 15 captured C units from loader
commit `f703f919c30c5b67958d35d40a4297cb3823ed78`, with original Xlib/XCB/Wayland,
Linux sorting and loader-search settings. Native `cc_import` exposes its link
interface. The binary retains its SONAME, RELRO/NOW and non-executable stack;
its dynamic dependencies contain only the target Linux runtime libraries.

`@chromium//native:vulkan_validation_runtime` builds the validation library and
original `angledata/VkLayer_khronos_validation.json`. It retains all 198 layer
C++ units plus 11 utility units across five captured targets. Source pins are
validation layers `83d96b88de7b85c3f29545170857e54e348421b2` and utility libraries
`4322db5906e67b57ec9c327e6afe3d98ed893df7`. BCR utility 1.4.349 renamed the NV
memory-decompression diagnostic helper required by the captured layer. Its exact
utility profile avoids changing validation behavior; Dawn still uses tested BCR
utility headers. Both components reuse native BCR Vulkan and SPIR-V providers.

The original Python JSON generator preserves layer version 1.4.328 and relative
library paths. `//:vulkan_validation_runtime_test` resolves those paths to the
actual native shared object, opens it, negotiates loader interfaces and checks
layer/extension discovery through the native loader. `//:vulkan_loader_runtime_test`
verifies the loaded library's identity, global Vulkan entry points, API version,
unavailable/malformed driver handling and Dawn's Vulkan discovery with validation
assets present. That negative-path test intentionally has no usable ICD; successful
software-Vulkan compute/raster calls are covered below. Browser assembly remains
unfinished.

## SwiftShader execution

`@chromium//native:libvk_swiftshader.so` builds the captured SwiftShader driver
from `5f1c459a11bb4899301e89609cbf7547f9f31e20`: 174 C/C++ units and one Marl fiber
assembly unit across 16 targets. Hermetic LLVM compiles the original Subzero JIT
and vendored LLVM support sources. The captured configuration does not use the
alternative LLVM JIT backend. Vendored Marl stays pinned with SwiftShader;
source processing removes only its upstream Bazel package boundaries.

Compatible native BCR providers supply SPIR-V tools/headers, Wayland 1.24.0.bcr.1
and libffi 3.4.7.bcr.5. Wayland scanner/protocol generation and configuration
checks use native compiler actions. No GN/Ninja/CMake invocation occurs in builds.
The driver's original version script, Bsymbolic, SONAME, RELRO/NOW and
non-executable stack remain intact. Dynamic exports contain only its four Vulkan
entry points; its C/C++ sources match the captured revision byte for byte.

`@chromium//native:swiftshader_runtime_test` lives beside the captured `angledata`
layout. It selects a real SwiftShader CPU Vulkan adapter through Dawn and the
native loader, requires the native validation library to be loaded, dispatches
WGSL compute and checks all 32 result words. A separate vertex/fragment pipeline
rasterizes a full-screen triangle; every copied RGBA pixel must be exact green.
Both paths report zero Dawn errors. The test preserves `VK_LAYER_PATH` while
Dawn temporarily scopes its own discovery environment. No null/mock driver is
used. Physical GPU execution and Skia GPU context integration remain unverified.

`//:wayland_runtime_test` exchanges a real client/server core-protocol sync over
a socketpair, exercising generated protocol and libffi callbacks. No display
server is required. `@chromium//native:dawn_native_runtime` now exposes all four
captured runtime artifacts: loader, SwiftShader, validation library and layer JSON.
Browser/Blink assembly, browser `--version` and headless page load remain unfinished.


ANGLE’s full EGL/GLES profile now builds in the combined workspace. Native BCR
X11/Xi/Xext/XCB and Wayland preserve its Linux display backends. Chromium’s VMA
fork (`cb0597213b0fcb999caa9ed08c2f88dc45eb7d50`) and Vulkan tools
(`d643b80d6ba8c191bc289fdda52867c3bb3c190b`) have no BCR modules; both build
from pinned source. Native pciutils 3.7.0 uses the SDK’s original Linux profile
and system libudev interface. EGL/GLES tests use SwiftShader, not the bundled
optional mock ICD. Standalone ANGLE publication still exposes its translator;
full renderer/browser integration and standalone runtime packaging remain pending.

ML prerequisites now reuse BCR CPUinfo `0.0.0-20250925-877328f`, FXdiv
`0.0.0-20201209-63058ef` and FlatBuffers `25.2.10`. All three match Chromium's
source pins; FlatBuffers tag resolves to `1c514626e83c20fffa8557e75641848e1e15cd5e`.
CPUinfo needs explicit Bazel 9 C++ rule imports. FXdiv and FlatBuffers use the
same BCR source archives with development tool dependencies separated from C++
consumption; FlatBuffers keeps upstream compiler targets and all generators.
`//:ml_support_runtime_test` runs native `flatc` on TFLite's
XNNPACK weight-cache schema, verifies valid, truncated and corrupt caches,
checks CPU topology and compares FXdiv quotient/remainder with
native division across boundary values and deterministic random inputs.

Chromium's pthreadpool uses Google's fork at
`f5a07eddbf4be8f23e29e60a2ccf66b78b71f119`, plus Chromium's `base::PostJob`
adapter. The available BCR module uses a different upstream revision.
`@chromium//native:pthreadpool` compiles the captured four translation units,
including original scheduler checks. `//:pthreadpool_runtime_test` checks serial,
automatic and four-thread pools, complete tiled coverage with partial edges and
empty 1D ranges. Empty tiled grids are outside the adapter's accepted range and
still trigger its original check.

Pinned TFLite and XNNPACK archives are registered by `build/ml_sources.bzl`.
All 1,310 upstream translation units referenced by the captured ML closure are
present. Chromium-owned wrapper sources come from the Chromium archive. Native
ML assembly and inference checks now pass; browser integration remains pending.

The complete captured TFLite/XNNPACK layer now builds 1,352 C/C++ units across
593 targets, with two original Protobuf actions and two FlatBuffers actions.
Ruy, Eigen, gemmlowp, FarmHash and NEON-to-SSE headers use Chromium's exact pins.
Chromium-owned FFT2D, logging adapters and ml_dtypes headers stay in its archive.
Public TFLite targets propagate the original TensorFlow version configuration.
The operation shim links native Abseil logging; assertions remain enabled.

`//:tflite_runtime_test` builds and verifies actual model buffers, runs float32
and signed-int8 inference with the builtin CPU kernels, then requires an actual
XNNPACK delegate node and checks both results. It resizes batch dimensions and
checks every output, including quantized saturation. Truncated models must fail
verification. The full runtime suite has 70 passing tests. This proves component
integration; browser `--version` and headless page load remain unfinished.


Media prerequisites now include native BCR Opus `1.6.1`, libvpx
`1.16.0.bcr.beta.3` and AOM `3.13.3.bcr.1`. Their C/C++ and NASM actions use
hermetic LLVM and native toolchains. The combined build optimizes these codec
kernels with `-O2`. The libvpx extension enables Chromium's high-bit-depth VP9
profile on x86_64, using full SIMD source lists and matching generated C/ASM/RTCD
configuration. One stale BCR source entry refers to a file absent upstream and
is removed; the upstream runtime dispatch definitions do not reference it.

FFmpeg keeps Chromium's exact fork at
`9e751092c9498b84bbb77e2e0689ef9f50fe608f`, its libavcodec 62 API and original
codec configuration. `@chromium//native:ffmpeg` compiles 206 C units and eleven
native NASM actions. It reuses native Opus and zlib providers. Opus's
private repository quote paths are excluded from FFmpeg's compilation context
so its `config.h` cannot shadow the captured FFmpeg configuration. Public Opus
headers and native linking context remain available.

`//:media_audio_runtime_test` encodes/decodes Opus audio, checks quality after
codec delay, exercises packet-loss concealment and rejects invalid packets.
It also demuxes an in-memory WAV through Chromium FFmpeg and checks every decoded
PCM sample. `//:video_codecs_runtime_test` encodes and decodes VP8, VP9 and AV1;
VP9 and AV1 preserve every pixel in both 8-bit and 10-bit lossless modes.
Chromium's captured C++ media closure now compiles against these BCR versions.
Browser process integration remains pending.
BCR dav1d's default profile omits assembly; the combined build now extends it
with the full Linux x86_64 SIMD profile.


Dav1d `1.5.4` keeps the official BCR source archive and adds 46 native NASM units,
x86 CPU detection and matching C/ASM configuration. Other platforms retain the
existing C profile. Its 8-bit and 16-bit implementations stay enabled. The video
test requires the native x86 CPU probe and active dispatch flags, decodes real
AOM-produced AV1 at 8/10 bits, checks every pixel and rejects malformed OBU data.

The captured GPU client/Viz layer now compiles 95 C++ units: GPU IPC client,
GLES2 implementation/helpers, raster implementation/interface, Viz common and
Viz client. Existing GPU service and generated Mojo providers are shared.
`//:gpu_client_runtime_test` drives the original common decoder through native
CommandBufferDirect and GLES2 command helpers. It checks 200 ring-wrap/token
cycles, immediate buckets, shared-memory transfers, bounds rejection without
bucket corruption and teardown ordering. This verifies common command transport;
GL/raster decoder rendering and full browser process integration remain pending.
The combined `//:components` build and all 70 runtime tests pass.


Captured media closure adds 40 native libraries/groups and 482 C/C++ units.
Four original Python actions generate Protobuf messages and PulseAudio stubs;
native CXX connects Chromium's original FLAC-only Symphonia Rust wrapper.
The Rust closure now contains 109 targets, 12 build scripts and 3,777 source inputs.
BCR FLAC `1.5.0.bcr.1`, libwebm `1.0.0.32`, CRC32C `1.1.0` and Snappy
`1.2.2.bcr.3` are shared. Header adapters preserve Chromium include paths;
CRC32C receives explicit rules_cc dependencies for Bazel 9. Snappy's public
virtual include root prevents SDK headers from shadowing the BCR implementation.

LevelDB, libgav1 and CDM API keep exact DEPS Git pins in `build/media_sources.bzl`;
compatible BCR modules were absent. Native LevelDB uses Chromium's file/thread
adapter. Native libgav1 parser preserves original public defines. ALSA headers
and link interface come from the pinned Linux SDK; PulseAudio keeps its original
runtime loader. Runtime libraries remain system-provided.

`//:media_runtime_test` encodes a multi-block FLAC stream with BCR FLAC, checks
every sample through native Rust Symphonia and Chromium's FLAC handler, verifies
reset and malformed-input rejection, then exercises real on-disk LevelDB
snapshots, atomic batches, lock exclusion, compaction and compressed persistence.
ICU initializes from pinned data before LevelDB logging. Browser executable,
Blink and cross-process media integration remain unfinished.


The complete captured `//cc:cc` closure now compiles: 913 new libraries/groups,
2,008 C/C++ units and 14 original Python actions. This includes 227 compositor,
405 network public-interface and 1,169 WebRTC units. Existing Mojo core/IPCz,
Perfetto, media, GPU and Viz providers are reused. Private metrics retains its
confidential-compute and Oak protocol dependencies.

`build/compositor_sources.bzl` pins Chromium's exact WebRTC, libsrtp and
federated-compute Git commits. BCR JsonCpp `1.9.6.bcr.2` is shared. Oak's
Chromium compatibility protocols come from the main source archive.
Mojo typemap configurations supply original trait headers. Field-trial
generators receive their Python helpers and schema as declared inputs.

Public C++ dependency adapters prevent codec repository quote paths from
shadowing Chromium headers. Chromium WebRTC override headers precede upstream
headers. The exported task-queue factory includes Chromium's original clock
provider. SRTP compiles with its private config directory; its private header
qualifies the config include so consumers cannot pick up Opus's config.
FFmpeg keeps its private config root in its own compiler options and exports
only public generated libavutil headers. PipeWire/SPA and ALSA interfaces come
from the pinned SDK; original runtime loading behavior remains intact.

BCR XDamage `1.1.6.bcr.1`, XFixes `6.0.2`, XRandR `1.5.4` and XRender `0.9.12`
are reused. XComposite `0.4.5` and XTest `1.2.3`, absent from BCR, add three
native C units with verified X.org archive checksums and BCR X11 dependencies.
DRM uses the pinned SDK's system-provided interface. Link-only providers preserve
the captured Chromium header context instead of adding inherited X11 headers
to every consumer.

Xshmfence uses a declared SDK link interface and bundles its matching
`libxshmfence.so.1`. Browser imports reuse the existing PartitionAlloc
base/core/shim/raw-pointer providers. Repeated archive sources stay owned by
their source-set dependencies; distinct source coverage stays unchanged.

`//:compositor_runtime_test` covers layer ownership/reparenting, transformed
occlusion and CORS credential checks. `//:webrtc_runtime_test` checks Chromium's
Location ABI, 200 ordered tasks, current queue, delayed dispatch and teardown.
SRTP checks real packet protection, authentication and replay rejection.
Confidential-compute checks real COSE/HPKE/AEAD and ECDSA, including malformed
keys, tampering and wrong associated data/recipient rejection. The manual Xvfb
test now exercises composite/render pixels, damage events, regions, pointer
injection and RandR through the native extension libraries.

Combined components and all 74 runtime tests pass, along with 17 metadata tests,
BCR staging and the manual Xvfb integration. Formatted compositor regeneration
is identical. Blink/browser assembly, `--version` and headless page load remain
unfinished.
