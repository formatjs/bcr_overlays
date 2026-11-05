# Native graph input

Current validation: Chromium **142.0.7444.59 Linux x86_64** builds and links with
native Bazel actions and hermeticbuild LLVM `0.8.26`. The untouched browser bundle
passes after relocation: exact `--version`, real HTTP HTML/JavaScript/CSS,
Promise execution, Unicode normalization, French Intl formatting and CSS layout.
Normal sandboxing stays enabled; `LD_LIBRARY_PATH` is unset.

Runtime assembly includes native PCI/NSS/NSPR DSOs, signed NSS module checksums
and verified Debian runtime packages. SDK link interfaces contain no executable
code and are never used as runtime libraries. Browser imports share PartitionAlloc
providers and remove duplicate archive sources owned by source-set dependencies.

The staged registry contains 28 modules and 1,376 Chromium overlay files. All
1,637 overlay hashes verify. Analysis against the actual pinned Chromium archive
passes at 379,665 configured targets. Full native compilation/runtime proof uses
the combined workspace; a complete standalone registry build and hosted BCR jobs
have not run. Nothing published.

The notes below record intermediate migration stages; their pending items reflect
status when written. Current build instructions live in the repository README.


`linux_x64.json.gz` captures Chromium 142.0.7444.59's resolved Linux x86_64
browser graph: 16,619 targets, 4,753 runtime files, 3,457 configuration files.
Every dependency resolves inside the snapshot. Every generated runtime file has
one producer. Source revision, DEPS digest, GN version and build arguments live
in `linux_x64.json.summary.json`.

GN runs only during maintainer extraction. Bazel builds consume committed
native rules; they never invoke GN or Ninja. Compiler command templates are
excluded. Host paths become `$SOURCE_ROOT` and `$LLVM_ROOT` in retained target
metadata; native translation must resolve these against declared sources and
registered hermeticbuild LLVM.

The graph is migration input, not a working browser build. Native C++/Rust,
host-tool, binding, resource and platform integration remain incomplete.

## Regenerate

Populate exact Chromium DEPS revisions, configure pinned GN and toolchains, then:

```sh
gn gen out/bazel-import --root-target=//chrome:chrome \
  --root-pattern=//chrome:chrome --ide=json --filters=//chrome:chrome \
  --filter-with-data
gn desc out/bazel-import //chrome:chrome runtime_deps \
  --root-target=//chrome:chrome --root-pattern=//chrome:chrome \
  --format=json > /tmp/chromium-runtime-deps.json
```

From this repository:

```sh
python3 tools/capture_native_graph.py \
  --project /path/to/chromium/out/bazel-import/project.json \
  --runtime-deps /tmp/chromium-runtime-deps.json \
  --source-root /path/to/chromium --llvm-root /path/to/hermetic-llvm \
  --revision 4b8153ab58d3c3f4c9f7e4baad9616ecf80db5fa \
  --gn-version '2285 (81b24e01531e)' \
  --output overlays/chromium/native/linux_x64.json.gz
python3 overlays/chromium/tools/import_buildflags.py \
  overlays/chromium/native/linux_x64.json.gz
python3 overlays/chromium/tools/import_generated_files.py \
  overlays/chromium/native/linux_x64.json.gz
buildifier -r overlays/chromium
```

Captured `args.gn` supplies Linux x86_64, noncomponent release configuration.
Chrome compiler plugins are unavailable in hermetic LLVM and disabled during
metadata extraction. Runtime features and checks keep upstream defaults.
Configurations require separate snapshots; do not apply these flags to other
architectures or platforms.

Native migration currently imports 118 Chromium-owned buildflag actions and
3,457 configuration-file writes. Perfetto's buildflag script belongs to its
separate source dependency and is excluded from Chromium-owned actions.

`@chromium//native:base` imports the complete Linux base source set: 425 C++
sources plus seven support sources. Original Rust logger uses native bindgen/CXX;
original JSON wrapper uses the pinned serde closure. Native upstream Python
actions generate build date and version headers. BCR GLib supplies the actual
event loop. Regenerate source lists, compiler settings and header bridges with:

```sh
python3 overlays/chromium/tools/import_base.py \
  overlays/chromium/native/linux_x64.json.gz --source-root /path/to/chromium
```

Runtime consumer covers Rust logging, C++ JSONReader, file I/O, GLib pumping and
ThreadPool replies. Native base/i18n adds 20 original C++ sources and file-backed
ICU/CED runtime validation. Browser build remains pending.

`native:grit_resources` runs 195 original GRIT actions, including shared resource
IDs. All 14,963 outputs retain locales, genders and image scales. Native BCR
Brotli handles compressed assets. Maintainer discovery declares Python runtime,
translated XTB files and every referenced GRDP fragment, including conditional
fragments read by the XML parser. Original GRIT assertions check output lists.
Discovery reads browser, WebUI and inspector catalogs. Build all three asset
groups, then supply the native output directory containing `gen/`:

```sh
bazel build @chromium//native:browser_assets @chromium//native:webui_assets \
  @chromium//native:devtools_inspector_assets
python3 overlays/chromium/tools/import_grit_actions.py \
  overlays/chromium/native/linux_x64.json.gz --source-root /path/to/chromium \
  --generated-root /path/to/native-bazel-outputs
```

Resource tests decode English/French packs, check disjoint ID ranges and merge
gender override packs with default translations. Binary tests validate compressed
SVG/shaders/Lottie against Chromium's original decoder, gzip descriptor bytes and
PNG resources at three scales. The maintained overlay imports all 195 actions:
14,963 outputs, 3,281 source inputs, zero unresolved producers in
[grit_targets.json](../bcr/overlay/native/grit_targets.json). All 195 native GRIT actions pass;
all 14,963 declared output files exist. The components pack decodes 45 resources;
its SSL-assistant and Safe Browsing protobufs match their generated bytes exactly.
Sixteen asset roots include the component SSL/Safe Browsing
protobufs and security/supervised-user bundles. Bundlers declare transitive
generated JS and source directories; reused Blink protocol generation remains
part of the asset build.

`native:blink_permission_strings_map` compiles the original permission-element
locale lookup. Its upstream generator reads declared source GRD and XTB files,
producing the combined translation GRD and C++ table. `//:permission_strings_test`
runs that C++ lookup against real packs: French camera text, language aliases
for English/Portuguese/Chinese, and missing language/message handling. The pack
reader honors its declared encoding.

`chromium_python_action` stages declared files at Chromium-relative paths,
executes upstream scripts with rules_python's interpreter, collects declared
outputs. Host executables retain FilesToRun/runfiles and execute through declared
prerequisites. Mojo and CXX expand their original per-source generator actions;
broader action translation and depfile handling remain pending. Bundled Python
imports are declared inputs.

Validate from `overlays/chromium`:

```sh
bazel test //:native_graph_buildflags_test
bazel build @chromium//native:all_buildflags \
  @chromium//native:configuration_metadata
```

Generated-header test compiles actual upstream header output, checking unwind,
expensive DCHECK and command-line sequence-check settings from this snapshot.

## PartitionAlloc

Native Linux targets under
`@chromium//base/allocator/partition_allocator/src/partition_alloc` compile
allocator base, core, malloc shim and raw pointers: 68 C++ sources. Importer uses
exact captured source lists and explicit header inventory. Runtime safety flags
retain backup-ref pointers, dangling checks, cookies, expensive DCHECKs, pointer
compression settings and thread isolation. No implementation substitutes.

Compiler modules, sysroot/include paths and upstream compiler-version markers
belong to the registered native toolchain. Native port omits those GN build
mechanisms and `-Werror`, retaining optimization and safety compiler flags.
Global C++ options in development and consumer `.bazelrc` files apply extensive
libc++ hardening and matching visibility settings to Chromium and LLVM's runtime.
Published module does not register a compiler; consumers must preserve that
runtime configuration when using these allocator targets.

```sh
python3 overlays/chromium/tools/import_partition_alloc.py \
  overlays/chromium/native/linux_x64.json.gz /path/to/chromium
buildifier -r overlays/chromium
cd overlays/chromium
bazel build @chromium//base/allocator/partition_allocator/src/partition_alloc:partition_alloc
bazel test //:partition_alloc_test //:allocator_shim_test
```

Test runs actual allocation, realloc content preservation, zero-fill and aligned
allocation with backup-ref pointer support enabled. Child process corrupts
trailing cookie; freeing must trap with allocator check. Staged BCR consumer runs
same test source. Additional shim consumer verifies `malloc`, `realloc`, `new` and STL storage
belong to PartitionAlloc pools, and links actual `raw_ptr` implementation.
Browser-wide allocator initialization and integration remain separate work.

## Mojo

`@chromium//native:mojo_bindings` builds browser's full captured Mojo Python
generator closure: 4,907 targets, one reused buildflag target. Includes 3,779
Python actions, parser import checks, both typemap validators, template
precompilation, C++/JavaScript/TypeScript generators and JS minification.
Two Blink enum-generator prerequisites also run natively.

`ChromiumFilesInfo` carries each declared file's logical source/build path.
Dependency outputs, including template ZIPs, remain explicit action inputs and
are staged in upstream's expected directory layout. Python uses a declared
module path and fixed hash seed. No host site packages or build backend.

GN-time inputs include response files and typemap configurations emitted during
metadata extraction, in addition to `generated_file` targets. Capture rejects
unavailable generated inputs. Native write actions reproduce their contents.

BCR `rules_nodejs@6.7.7` supplies exact Node 22.11.0. Upstream Node version check
runs before minification. Chromium's complete prepatched Node dependency archive
comes from its pinned DEPS entry, with generation and SHA-256 preserved. This
includes Terser 5.37.0, TypeScript 5.8.2 and Chromium's Trusted Types patches.
Native repository downloads unpack source only; npm and package scripts never
run. Nested dependency paths remain intact.

```sh
python3 overlays/chromium/tools/import_node_deps.py /path/to/chromium
python3 overlays/chromium/tools/import_mojo_actions.py \
  overlays/chromium/native/linux_x64.json.gz /path/to/chromium
buildifier -r overlays/chromium
cd overlays/chromium
bazel build --jobs=8 @chromium//native:mojo_bindings
bazel test //:mojo_control_test
```

Generated declarations use 31 shards and interned file/argument tables.
`mojo_targets.json` maps original GN labels to native targets for graph audit.
`mojo_control_bindings` exposes control-protocol artifacts separately. Consumer
test loads actual parser output and checks reserved message IDs, union/nullable
semantics and fixed wire layouts. Native C++ runtime libraries now build; see
[Mojo runtime](#mojo-runtime). Remaining browser interface consumers need ports.

## ipcz runtime prerequisite

`native:ipcz` uses the independent ipcz overlay's build macro with `native:base`.
It preserves Chromium's support implementation and compile flags. Legacy include
paths forward to the overlay's canonical public/static API headers. Standalone
ipcz uses its original support implementation and stock BCR Abseil.

`//:ipcz_test` runs the same test source against each implementation: two connected
nodes, 65 KB binary data, receive-capacity failure without consumption, portal
transfer and communication, peer closure, and invalid-input rejection. Chromium
checks its original include paths too. These use the original reference driver;
the separate Mojo runtime test below exercises its actual Chromium driver.

## Mojo runtime

`native:mojo_cpp_bindings` builds original Linux core, ipcz driver, embedder,
platform, C/C++ system, IPC message support and C++ bindings. Native control
schemas come from the existing upstream parser/generator actions. The production
InterfaceProvider schema adds a small concrete C++ consumer; the imported closure
contains 128 C++ sources and preserves original per-target flags and defines.
`native:mojo_base_types` adds all 107 original base-value, shared-schema and
typemap sources, including unguessable-token validation.

Platform channels use the original two Unix-address helpers from net. Linux core
sources have no crypto calls. Complete net remains pending; crypto now uses the native target below.
Original validation and library RTTI/exception settings remain; consumers match
Chromium's configuration.

`//:mojo_runtime_test` initializes the real broker and IPC thread, checks binary
message/data pipes, shared-buffer transfer/coherence, invalid operations and peer
closure. It launches the same binary as a client process, exchanges invitations,
transfers 65 KB and shared-memory handles, and verifies writable cross-process
coherence. Multi-pipe invitations use upstream ipcz's integer attachment slots.

The generated InterfaceProvider client/server also runs across that channel,
checking embedded-NUL strings and message-pipe arguments. A malformed raw message
must disconnect its binding without dispatch. Browser service implementations,
remaining generated interface consumers and full browser assembly remain pending.

```sh
python3 overlays/chromium/tools/import_mojo_runtime.py \
  overlays/chromium/native/linux_x64.json.gz --source-root /path/to/chromium
cd overlays/chromium
bazel test //:mojo_runtime_test
```

## Crypto and CBOR

`native:crypto` compiles all 29 original Linux crypto sources, including NSS
initialization/key utilities. `native:cbor` compiles all five CBOR sources.
Per-target flags and defines come from the captured GN graph. Native NSS carries
its signed modules; BoringSSL shares the existing BCR snapshot with a build-only
PKI adapter. Original include paths forward to 137 BoringSSL headers.

`//:crypto_runtime_test` checks SHA-256, RFC 5869 HKDF, AES-256-GCM golden bytes and
authentication failures, PKCS#8 trailing-data rejection, NSS/BoringSSL key exchange
and signature interoperability, COSE P-256 coordinates and CBOR rejection. PEM file
helpers exercise binary data, label filtering and duplicate-block rejection.

```sh
python3 overlays/chromium/tools/import_crypto.py \
  overlays/chromium/native/linux_x64.json.gz --source-root /path/to/chromium
cd overlays/chromium
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build \
  //:crypto_runtime_test
```

The registry must include the dependency entries shown in the parent README.

Regenerate original include-path adapters from the pinned Chromium checkout and
matching shared dependency sources:

```sh
python3 overlays/chromium/tools/import_bcr_headers.py \
  overlays/chromium/native/linux_x64.json.gz --source-root /path/to/chromium \
  --abseil-source /path/to/shared/abseil --boringssl-source /path/to/shared/boringssl
```

## URL and origin wire types

`native:url` compiles all 26 Linux URL parser, canonicalizer and origin sources
with Chromium's ICU fork. `native:url_origin` and `native:url_scheme_host_port`
add the original three Mojo traits and six generated C++ sources. Imported flags
and defines come from each original GN target.

`//:url_runtime_test` uses file-backed ICU data. It checks URL canonicalization,
IDNA, IPv4 normalization, invalid hosts/ports and same-origin behavior. Production
Mojo serialization checks tuple and opaque origins, preserving opaque nonces;
malformed URL/origin/host payloads and truncated input must fail decoding. No test
schema or alternate serializer replaces the production wire representation.

```sh
python3 overlays/chromium/tools/import_url.py \
  overlays/chromium/native/linux_x64.json.gz --source-root /path/to/chromium
cd overlays/chromium
bazel test //:url_runtime_test
```

## WebUI assets

`@chromium//native:webui_assets` imports 1,435 original asset targets, including
163 TypeScript compilations, 153 ESLint checks, HTML/CSS wrappers, preprocessing,
Rollup bundling, Terser minification and GRD generation. Dependencies retain
original validation gates and paths. Native copy actions preserve generated
source layouts; dependent TypeScript projects receive their source definitions.

`webui_targets.json` records 31 pending prerequisites and dependent targets:
native code-cache generation and Catapult tracing assets. These branches remain
excluded until their real producers are ported.

`//:webui_test` executes emitted assertion and PromiseResolver modules with pinned
Node. Compiler checks exercise Chromium's TrustedHTML setter patch and verify
that a type error fails without emitting JavaScript. Downloads-page checks decode
the actual pack, verify its module reference and compare packed JS with original
minifier output before checking module syntax. Traces-internals executes its
generated TS Protobuf codec against the same golden wire bytes checked by three
C++ Perfetto APIs, including unknown-field and truncated-input checks.

The original TS Protobuf Python wrapper runs through a native tool adapter with
pinned Python/Node runfiles. The adapter selects rules_python's script bootstrap
and copies its launcher so composed runfiles resolve correctly. No upstream
plugin source changes or host Python lookup.

```sh
python3 overlays/chromium/tools/import_webui_actions.py \
  overlays/chromium/native/linux_x64.json.gz --source-root /path/to/chromium
cd overlays/chromium
bazel build @chromium//native:webui_assets
bazel test //:webui_test
```

After a successful asset build, `import_grit_actions.py --generated-root` accepts
the native Bazel output directory for input discovery. It copies artifacts into
the temporary maintainer source tree to inspect generated GRDs; published rules
depend on native generators and never embed those generated assets.

## Protobuf integration

Native host-tool adapters stage declared executables through symlinks and carry
Bazel runfiles into generator actions. Upstream `protoc_wrapper.py` invokes the
actual BCR compiler built with hermetic LLVM; no prebuilt host protoc or foreign
build system.

Chromium's source baseline is Protobuf 32.0. Bazel 9.2's own `bazel_tools`
dependency requires 33.4, which version resolution selects. Native integration
explicitly reuses BCR `protobuf@33.4` and its matching compiler/runtime.
Compatibility is checked against unchanged Chromium schemas rather than assumed
from module-name presence.

`protobuf_config.bzl` scopes `PROTOBUF_INTERNAL_BOUNDS_CHECK_MODE_ABORT` and
`GOOGLE_PROTOBUF_NO_RTTI` onto both BCR compiler and runtime dependencies. Runtime
headers export matching defines to consumers. Safety configuration requires no
consumer-wide Protobuf options. LLVM runtime hardening remains configured as
above.

`@chromium//native:variations_proto` generates and compiles original Variations
seed, study, layer and stored-seed schemas. Native test checks fixed wire bytes,
unknown-field retention, nested study/layer round trips, required-field rejection,
Chromium's disabled UTF-8 validation policy, and fatal repeated-field bounds
checks with `NDEBUG` defined. Broader Chromium Protobuf API integration remains
pending.

```sh
python3 overlays/chromium/tools/import_proto_actions.py \
  overlays/chromium/native/linux_x64.json.gz
buildifier -r overlays/chromium
cd overlays/chromium
bazel test //:variations_proto_test
```

## Rust prerequisites

Pinned Chromium Rust compiler, original global allocator, native C++ bindgen,
CXX compiler/runtime, prelude/import macro and logging crate now build through
BCR Rust rules. Native build scripts preserve captured features and lint policy.
Allocator and generated CXX runtime tests pass in staged consumers and development
harness. Linux base runtime tests also exercise original Rust logger and JSON
integration. Additional browser crate integration remains pending. See
[Rust configuration](../README.md#native-rust-and-cxx).


The combined workspace now builds the captured ANGLE EGL/GLES runtime with its
GL/Vulkan/Dawn backends. `@chromium//native:angle_runtime_test` verifies a real
SwiftShader Vulkan shader draw and exact pixel readback without a display server.
`angle_runtime_edges.json` records runtime-only dependencies separately from
C++ dependencies; its source and graph hashes are checked during import.


GPU command/common and GLES2 protocol libraries now build from the captured
source lists, with shared-image formats and generated single-planar Mojo types.
`//:gpu_protocol_runtime_test` verifies cross-process shared command memory,
discardable handles and image-layout bounds. The service decoder remains pending; the captured
Chromium GL wrapper now renders through SwiftShader. `gl_runtime_edges.json` records the wrapper’s
ANGLE/SwiftShader/loader runtime dependencies.


`@chromium//native:gfx_x11` now builds the native X11 connection/protocol and
platform-event layer. `tools/run_x11_integration.py` verifies it against a private
real Xvfb server; BCR XCB’s Linux abstract-socket compatibility patch keeps the
test sandboxed. The GL wrapper and its Linux UI/tracing dependencies now build; Browser initialization remains pending.


The captured Linux graphics-buffer wrappers now build as `:linux_gbm`,
`:linux_drm`, `:native_pixmap_usage` and `:x11_gpu_memory_buffer_support`.
They retain system GBM through the pinned SDK interface. Format/usage checks
and the real Xvfb missing-DRI3 rejection path pass; physical DRM allocations and
DMA-BUF transfers remain unverified.


Shared browser services now build: metrics, tracing, preferences, variations,
version metadata and their generated protocols. `:browser_metrics` and
`:browser_tracing` reuse existing native base/network/Perfetto providers and a
native pinned protobuf JavaScript plugin. `//:browser_services_runtime_test`
checks persistent preferences, metrics/variation data and fragmented trace
packets. The Linux UI/GL closure now builds; full browser assembly remains pending.


The captured Linux UI/GL closure adds 351 native C/C++ units, with BCR xkbcommon
and native Bison generation. `@chromium//native:gl_runtime_test` renders an ES3
triangle through Chromium’s actual context and GL dispatch into SwiftShader,
with exact pixel readback. GPU service decoder and browser/Blink assembly
remain pending.


Ozone and GL initialization add 411 native C/C++ units and 39 original generator
actions. Headless, X11 and Wayland stay enabled. The headless Ozone runtime test
uses the public GL factory and verifies SwiftShader pixels. BCR GLib's native
shared libraries prevent duplicate GLib state when desktop libraries load.
Browser process and renderer assembly remain unfinished.


The captured browser V8 profile now builds with native Torque/mksnapshot tools,
external startup data, Temporal, Perfetto and sandbox checks. Its runtime test
verifies sandbox-backed buffers, Temporal/DST, Chromium ICU behavior, Wasm and
microtasks. Native Rust dependencies total 109 targets and 12 build scripts.
The full browser process remains unfinished.


GPU service compilation now passes: 355 C/C++ units include GLES2/raster
decoders, shared images, GPU configuration, persistent cache, Dawn wire and
pinned libyuv. Existing generator outputs are reused with declared action
inputs. GL/raster decoder rendering and browser assembly remain unverified.


The full captured TFLite/XNNPACK layer now builds 1,352 C/C++ units across 593
targets, retaining original SIMD profiles, quantized inference, Ruy and Chromium
pthreadpool integration. Four generator actions use native Protobuf/FlatBuffers
tools. `//:tflite_runtime_test` checks builtin and confirmed XNNPACK-delegated
float/int8 inference, dynamic batch resizing and invalid-model rejection.
Browser/Blink integration remains pending.


Chromium FFmpeg now builds its captured codec profile with 206 C units and eleven
native NASM actions. BCR Opus, libvpx and AOM are shared; libvpx's x86_64 profile
retains high-bit-depth VP9. Audio tests cover Opus, WAV demuxing and exact PCM
samples. Video tests cover VP8 and lossless VP9/AV1 at 8/10 bits. Browser media
integration remains unfinished. Native dav1d SIMD now verifies AV1 at 8/10 bits.


GPU IPC/GLES2/raster clients and Viz common/client now compile 95 captured C++
units. The native command-buffer test executes original common decoder commands
through a real ring buffer, token fences and shared memory; invalid ranges must
fail without changing bucket data. Full GL/raster service rendering and browser
assembly remain unfinished. Combined components build and 70 runtime tests pass.


## Media pipeline and storage

`@chromium//native:media` compiles the full captured media closure: 40 native
libraries/groups, 482 C/C++ units, four original Python actions and one native
CXX bridge. BCR codecs are shared. Exact DEPS repositories supply LevelDB,
libgav1 parser and CDM API headers. Symphonia keeps Chromium's FLAC-only profile;
Rust prerequisites now total 109 targets and 12 build scripts.

`//:media_runtime_test` validates exact FLAC PCM through Symphonia and Chromium's
handler, reset/malformed input, then real LevelDB snapshots, atomic batches,
lock exclusion, compaction and compressed persistence. ICU data and Linux audio
interfaces are declared dependencies. Combined components and 70 runtime tests
pass. Browser executable and headless page load remain pending.


Compositor migration now imports the complete `//cc:cc` dependency closure:
913 new libraries/groups, 2,008 C/C++ units and 14 Python actions. Existing Mojo
core/IPCz, Perfetto, media, GPU and Viz providers are shared. The closure includes
227 compositor units, 405 network public-interface units and 1,169 WebRTC units.
Private metrics retains confidential-compute and Oak protocols.

Native SRTP checks pass encrypted packet round trips, tamper rejection and
replay protection. Native confidential-compute checks pass COSE/HPKE/AEAD round
trips, ECDSA verification and tamper/context/key rejection. Compositor compilation,
Chromium WebRTC override priority and native task-queue dispatch now pass.
Combined components and 74 runtime tests pass. Manual Xvfb checks verify real
composite/render pixels, damage events, regions, pointer injection and RandR.
Browser assembly and headless page load remain pending.

Blink platform now imports 735 libraries/groups/tools, 4,500 C/C++ units and 43
original generators. Native character tables and the full Web IDL database build.
Font-format Rust/CXX tests pass static/COLRv0/COLRv1 recognition and malformed
input rejection. CrabbyAVIF tests pass animated 8/10/12-bit decoding, alpha
conversion, seeking and truncation rejection against BCR dav1d and pinned libyuv.
Rust prerequisites total 114 targets and 12 build scripts.

Inspector overlay assets build through three original DevTools actions and two
copies, producing 47 outputs. Exact DEPS sources include its npm dependencies;
pinned Node and esbuild run without installers. GRIT now covers 187 actions,
including the inspector resource pack. Eight browser resource actions remain.

Full platform compilation and linking pass. Runtime integration passes UTF-8
rejection, UTF-16 grapheme boundaries, string interning, generated Unicode
properties and CSS color lookup. Standalone test registers its embedder locale
and initializes Blink's locale singleton. Browser executable and headless page
load remain pending.

Combined components and 77 runtime tests pass at the platform milestone.
Platform regeneration matches byte-for-byte.

Blink core import adds 36 libraries/groups, 53 original generators and 3,854
C/C++ units. Existing platform, Mojo, WebUI and DevTools producers are shared.
Full core compilation, archive linking and parser executable linking pass.
Inspector protocol actions declare recursive PDL imports and versioned baseline
files. Bindings, protocol compatibility, probes and event-handler generators
pass with their original Python runtimes and templates.

Native modules import adds 267 further libraries/groups, 3,040 C/C++ units and
six generators. Compilation is in progress with content.

Native content import adds 612 further libraries/groups, 4,092 C/C++ units,
71 generators and two copies. It reuses existing Perfetto producers and native
host executables;
`llguidance` expands the Rust import to 129 targets and 15 build scripts.
The combined content/assets build now includes modules and the additional Rust
crates. All 77 module/content generators pass, including policy YAML, vector
icons, protobuf descriptor processing and the Web IDL file-list check. OpenScreen
and PDFium have pinned source providers; FLAC headers retain their BCR owner.
The Chromium source ownership audit reports no missing inputs. The first C++
pass completed with missing header declarations and three resource packs.
Generator export headers, the origin-trial mixin, CUPS and Puffin lookup paths
now have declarations; their next compile check awaits those resource packs.

`//:blink_core_runtime_test` checks HTML tokenization across every input chunk
size, entity decoding, malformed input recovery and CSS tokenization. It passes
with the original generated tokenizer names initialized by the fixture.
Combined components and 79 runtime tests pass at the core milestone.

Browser resources now have an initial import: 1,374 actions and two host-tool
C++ units. `import_cpp_layer.py --layer browser --assets-only` imports the eight
remaining GRIT prerequisite roots before full executable assembly. DevTools,
tracing and code-cache generation are being validated. Recorder bundling,
UI-string collection and Catapult tracing now generate their real outputs.
Generated-output providers carry transitive DevTools files without staging
runtime source trees as resource-pack inputs. Catapult declares its Python,
Polymer and tracing assets; the UI-string collector declares scanned directories.
The broader asset build found disappearing shared-cache repository contents.
Forced restoration now passes with fetched repositories inside the output base;
the combined workspace disables the shared extracted-repository cache.

The pinned SDK contains stripped link interfaces, not executable shared libraries.
`import_platform_runtime.py` resolves 94 library requirements to 88 original
Debian packages, including Qt 5/6. Optional downloads verify each original file
against the SDK's package checksum and require loadable code or data. All 88
packages now have SHA-256 pins. Native Debian container/payload extraction passes;
CUPS, Pango and both Qt widget libraries load from the resulting 94-library
closure.
Native staging now provides 71 libraries for host generators and 94 for the
browser. Four GLib libraries use the rebuilt BCR providers. Link rules add
adjacent `lib/` lookup; the snapshot tool selects the SDK-compatible glibc 2.31
execution platform. Native snapshot generation now passes with this wiring,
producing a 4,187,848-byte `v8_context_snapshot.bin`. The real Rollup Web Vitals
bundle also passes at 15,201 bytes. Browser execution remains unverified.
Executable-dependency staging and the same execution platform for all 14
code-cache actions pass importer preflight; overlay regeneration waits for the
live build's exit.

Full-browser preflight resolves 2,871 libraries/groups/tools, 1,952 generators
and 12,508 C/C++ units after sharing ICU and the BCR Protobuf compiler;
the Qt shims retain their original runtime-only edges. Ten missing source
repositories are registered through `build/browser_sources.bzl`.
PDFium shares the existing BCR `fast_float@8.2.4` provider with V8. Browser Rust
preflight (`import_rust_crates.py --browser`) resolves 133 targets, including QR
generation and user-data ZIP bridges. An isolated full browser/bundle build is
running with four jobs and the shared disk cache; compilation has not passed.
The first pass exposed undeclared Python imports in accessibility manifests,
flags, JSON-schema registration and binary-proto generators. Importer fixes add
their source closures and native tools. All eight native generator probes now
pass: accessibility manifest, flags, feature compilation, binary encoding,
Safe Browsing binary proto, two API registration bundles and supervised-user
JavaScript preprocessing. The pending
integration patch stages the matching BCR Python runtime through `PyInfo`,
preserving Protobuf's version checks. Schema bundles receive default API headers
and explicit `implemented_in` headers; generated registration files contain the
DeveloperPrivate and ControlledFrameInternal entries. The GRIT preprocessor's
complete Python closure produces all three supervised-user scripts without
remaining `<if expr=...>` directives.
The neterror ESLint action also passes in an isolated native build. Actions
with Node inputs receive the declared NPM closure, including Python wrappers
that invoke Node. Lint remains enabled.
All 139 browser schema generators pass in a separate native build. Declared
inputs include schemas searched by `NamespaceResolver`, including paths from
`--include-rules`; this resolves `contextMenus` and `extensionTypes` references.
The language generator produces its 73,950-byte header with declared Jinja
inputs. Both Dom Distiller proto generators pass with a hermetic Python tool;
Chromium's Protobuf extras compiler builds against BCR `protoc_lib`. Host tools
receive dependency header forwarders. Python children clear inherited runfiles
variables so their launchers resolve their own inputs. These changes are
integrated into the maintained overlay.
A 180-target native regression passes with this runner: all browser schema
generators, 32 Protobuf extras actions, flags, accessibility, binary protos,
GRIT preprocessing, ESLint, Rollup and a TypeScript proto plugin.
Blink's original 200-percent resource repack also passes with the complete
GRIT Python closure; the old full build had exposed its missing `grit` import.
Isolated analysis of `browser` and `browser_bundle` passes with these fixes:
372,576 configured targets with native XSLT, an 8-GiB JVM heap and no executed actions.
Root defaults cap Bazel at eight jobs and an 8-GiB heap. Size concurrent builds
from cgroup limits; host CPU affinity and `/proc/meminfo` can overstate capacity.
Schema headers reuse their native generators;
PartitionAlloc reuses existing buildflags instead of declaring duplicate outputs.
The isolated search-engine generator also passes, producing the original
`prepopulated_engines.h` and `.cc` through its existing Blink provider.

Qt 5/6 shims now pass an isolated native Bazel compile/link probe using the
original interface, shim and generated moc sources. Hermetic LLVM uses the
captured SDK's GNU headers/runtime for this boundary. ELF checks reject libc++
symbols and require adjacent `lib/` lookup; both DSOs load without
`LD_LIBRARY_PATH`, reporting Qt 5.15.2 and 6.4.2. Run
`tools/check_qt_shims.py <bundle-directory>` to repeat the loader checks.
Both loader checks also pass after replacing the SDK GLib family with the four
rebuilt BCR libraries; the loaded GLib reports 2.82.2.
The Qt bridge keeps its GNU SDK headers in `implementation_deps`. Browser-side
Qt code uses LLVM's libc++; compiler dependency files verify the split. Both
original libraries compile, and rebuilt Qt 5/6 shims pass GNU ABI and relocated
runtime-loader checks with the private dependency.
Integration is applied; the original patch is retained as
`native/browser_integration_applied.patch`. The maintained overlay includes
2,869 libraries/tools, 1,956 generators and 12,481 C/C++ units. Brotli encoder
and common code reuse BCR providers. The importer retains the captured S2,
TensorFlow Models, Puffin and SentencePiece include roots and ICU shims.
Chromium's proto_extras header
includes Abseil Cord instead of declaring it outside the inline namespace.
Captured include roots inside each target's source tree and project ancestors
are retained; mapped external repositories keep their own include providers. This restores local
configurations for 16 targets, including libtess2, LZMA and zxcvbn.
Nine isolated native regression targets pass: proto_extras, S2 and its language
locator, TensorFlow custom operations, Puffin, BCR Brotli encoder, SentencePiece,
libtess2 and Ink.
Crashpad's tool_support also passes a native compile after restoring its parent
project include root. Its HTTP transport uses BCR curl 8.12.0.bcr.1 headers;
the browser bundle stages native `libcurl.so` for Crashpad's `dlopen` lookup.
The BCR shared-library test passes with the pinned BoringSSL. The relocated DSO
loads and creates a curl handle without `LD_LIBRARY_PATH`; its only runtime
dependencies are GNU system libraries. Crashpad HTTP transport and runtime-copy
targets also pass.
Printing Mojo traits use local duplicate comparators instead of specializing
`std::less`. This preserves the comparison bodies while avoiding libc++ 23's
transparent-comparator optimization. The original native traits target compiles
successfully with the overlay.
Generated GTK stubs compile against an explicit SDK header provider covering
GTK 3, GDK Pixbuf, Pango, Cairo and ATK. GLib headers and libraries continue to
come from BCR. The isolated stub target passes without changing the live SDK.
The staged SDK has the same 502 GTK provider headers, with matching contents,
inventories and GTK provider definition.
ALSA and Pulse headers use scoped virtual include trees, preventing the SDK's
GNU C headers from shadowing LLVM's libc++ wrappers. Both original audio targets
pass compilation, including 14 compiler actions in Linux sandboxes backed by a
private RAM filesystem. Local C++ execution is unsuitable for this source layout:
vendored headers can precede the declared BCR forwarding headers.
Three further source fixes pass native compilation: an explicit predicate in
autofill's field counter, owned strings at libphonenumber's parsing boundary,
and a quoted Abseil include in actor geometry. These preserve existing behavior
while adapting to the selected compiler and dependency APIs. Both original
library targets pass with `--output_groups=compilation_outputs`, including
three sandboxed compiler actions for the changed files.
Cookie Store's subscription lookups use explicit reference projections instead
of taking `unique_ptr::operator*` addresses. Its changed source compiles in the
full browser build with libc++ 23. Password-form copying uses the same adapter
and also compiles successfully in the full build.
GPU list revision metadata reproduces the DEPS `lastchange.py` header hook using
the captured Chromium commit and upstream header formatter. Native header
generation passes. The generated header is private to the GPU internals unit,
which compiles successfully in the full build.
Content startup includes BCR cpuinfo's public header directly. Its native object
and compiler dependency trace verify the existing cpuinfo dependency is used;
XNNPACK remains enabled.
Privacy notice headers use quoted Abseil includes. TensorFlow Text's spanning-tree
headers explicitly select Chromium's status/logging shims. Both notice catalog
and phrase-segmentation model sources compile in the full build.
The packed-resource integrity generator declares `action_helpers.py` and its
`gn_helpers.py` import. Its native output passes independent SHA-256 checks
against all three actual resource packs, including the 14,996,244-byte
`resources.pak`.
Registry staging validates. Standalone browser-bundle analysis passes from the
maintained consumer with 379,635 configured targets and no executed actions.
The registry-only check also passes after Bazel extracts the original 1.4 GB
Chromium archive and applies all 1,376 overlay files. No Chromium source override
is used. Native foundation and histogram generator probes pass from that
repository, including eleven sandboxed actions. Toolchain caches are reused.
Browser compilation and runtime checks remain pending. The runtime-manifest
export belongs to the Chromium subpackage.

Isolated probes mount both the main dependency tree and the separate SDK source
workspace read-only. A native PipeWire header compile fails without the SDK
mount and passes with it; the SDK provider already declares the required headers.
That probe also exposed libaddressinput's angled RE2 includes and included GRIT
message map. The importer now retains the captured RE2 include root through a
repository label and declares `en_messages.cc` as a localization input. These
fixes pass the isolated native libaddressinput build, including its dependency
closure and static archive. The integration patch also declares the matching
BCR RE2 dependency.
An isolated native storage build also passes after excluding Open Screen's
obsolete vendored Protobuf headers from its header provider. They otherwise
shadow Chromium-qualified forwarding headers and mix incompatible Protobuf
versions. This source-provider fix is integrated.
Isolated Open Screen overrides also need their source directory mounted into
the sandbox's private `/tmp`. Without it, three native protobuf actions cannot
read declared source files. All three pass with the mount; a forced storage
recompile confirms the obsolete Protobuf headers remain excluded.
The expired-histogram generator also passes natively after declaring the branch
date and version files passed through attached short options (`-d../../...`,
`-m../../...`). The importer now discovers these source arguments.
Native generator tools also select the GNU 2.31 execution platform. The default
host platform could not satisfy SDK ALSA's `GLIBC_2.29` math symbols when linking
the country-name generator. Its native link and upstream header generation pass
with the constraint.
Standalone module staging bundles the combined source repositories and published
dependency wiring. The current staged snapshot includes 1,376 Chromium overlay
files; full browser compilation and launch remain pending.
`tools/stage_compatibility_modules.py` stages the 13 remaining compatibility
entries together from tested source trees. Their staged source, overlays and
provenance live in `compatibility_registry/` at the workspace root.
Each consumer declares one compatibility module plus compiler dependencies;
all 13 pass.
The combined consumer also builds 15 native library targets with hermetic LLVM;
its cpuinfo runtime test passes. The codec modules preserve
the tested NASM checker dependency floor. Each entry includes an independent
BCR consumer and Linux presubmit job; the staged cpuinfo runtime test passes.
Hosted BCR jobs have not run. Bazel applies dependency overrides
only in the root module ([module reference](https://bazel.build/rules/lib/globals/module#single_version_override)).
Native XSLT supplies direct single-libxml wiring and removes its root flag.
Hermeticbuild Node.js selects patched source, V8 and ICU repositories through its
[module extension](https://github.com/hermeticbuild/nodejs/blob/main/nodejs/extensions.bzl).
That is a candidate packaging boundary for the combined Chromium source and
compatibility setup. A standalone consumer build still needs verification.

Native runtime assembly now passes a relocatable bundle probe: 97 real files,
including Qt, rebuilt BCR GLib and an executable fixture. The assembler copies
bytes rather than source symlinks; loader checks pass after moving the tree.
The `browser_bundle` rule covers all 4,753 captured GN runtime files
plus platform libraries. This has not yet assembled or validated Chromium.
After assembling the browser, run `tools/check_browser.py <bundle-directory>`.
It checks the exact version and loads a local HTTP page from a separate working
directory. HTML, JavaScript and CSS requests must all reach the fixture server;
Promise execution, Unicode, Intl and layout checks must pass. It removes
`LD_LIBRARY_PATH` to exercise the staged libraries.
Use `--no-sandbox` only on test hosts without Chromium sandbox support.
Full-browser analysis also exposed duplicate PartitionAlloc buildflag generation;
the importer now reuses the existing native buildflag catalog.

The native XSLT target compiles Chromium's vendored `fe508f2` fork:
19 C sources and 27 headers with captured Linux C flags. It depends directly on
`native:libxml`, removing the BCR libxslt module, compatibility override and
root-only provider flag. The existing runtime test passes parameters, XPath,
attribute IDs, temporary trees and repeated transformations. Link inputs contain
all 19 native XSLT objects and Chromium's libxml; neither BCR library is linked.
Full browser/bundle analysis also passes with this dependency graph.
Regenerate with `tools/import_xslt.py <graph> --source-root <source-directory>`.
This wiring is integrated; full browser runtime validation remains pending.
