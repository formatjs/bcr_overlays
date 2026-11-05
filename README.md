# Chromium native Bazel build

One workspace builds Chromium 142 and its dependencies with native Bazel actions.
All maintained overlays share one dependency setup and hermeticbuild LLVM.
Compatible BCR modules stay shared; pinned Chromium forks keep their patches.
Linux x86_64 browser and runtime bundle build successfully. Relocated bundle
reports `Chromium 142.0.7444.59` and passes a real headless HTTP page check with
external JavaScript/CSS, Unicode normalization, Intl formatting and layout.
Validation uses the normal Chromium sandbox and no `LD_LIBRARY_PATH` override.

The existing `overlays/` directories organize build rules and source pins.
They no longer need separate registry staging for the main build.

- [Chromium](overlays/chromium): native base, Mojo, network/SQL, geometry, fonts, image codecs, GPU command protocol, X11 connection, browser services, Linux UI/GL and generators; Linux browser and runtime bundle validated.
- [V8](overlays/v8): native engine, snapshots, WebAssembly and Intl validation.
- [NSS](overlays/nss): patched Linux PKCS#11, persistent key databases and signed FIPS modules.
- [NSPR](overlays/nspr): native Linux runtime and PLC/PLDS support for NSS.
- [ipcz](overlays/ipcz): native standalone and Chromium implementations, real transport/portal tests.
- [Perfetto](overlays/perfetto): native protocol compilers, browser tracing, service and IPC runtime.
- [Chromium ICU](overlays/chromium_icu): pinned fork, embedded/file data validation.
- [Dragonbox](overlays/dragonbox): V8 decimal conversion dependency, absent from BCR.
- [Linux Syscall Support](overlays/linux-syscall-support): pinned native syscall header.
- [Compact Encoding Detection](overlays/compact_enc_det): Chromium's pinned HTML5 detector.
- [BoringSSL](overlays/boringssl): existing BCR snapshot with public Chromium PKI adapter.
- [Abseil](overlays/abseil-cpp): existing BCR module update preserving Chromium hardening.
- [FP16](overlays/fp16): Bazel 9 compatibility update to existing BCR module.
- [Skia](overlays/skia): full captured Chromium profile in combined workspace; standalone raster core/path operations.
- [ANGLE](overlays/angle): native EGL/GLES runtime, Vulkan/Dawn backends, WebGL shader compiler.
- [Dawn](overlays/dawn): native backends, Tint, validated software-Vulkan execution.
- [SwiftShader](overlays/swiftshader): native Subzero driver, compute/raster readback.
- Standalone entries planned: [WebRTC](overlays/webrtc), [PDFium](overlays/pdfium).

WebRTC, PDFium, Dawn and SwiftShader build inside Chromium’s combined workspace.
Their standalone registry entries remain planned in
[overlays.json](overlays.json).
See [dependency audit](docs/dependency-overlays.md) for compatibility findings.

## Development

```sh
bazel build //:components
bazel test //:runtime_tests

# Individual components use the same dependency setup.
bazel build //:quiche //:v8 //:skia //:angle
python3 -m unittest discover -s tests

# Full browser and runtime bundle.
bazel build --config=browser @chromium//native:browser @chromium//native:browser_bundle
bundle=$(bazel cquery --config=browser --output=files @chromium//native:browser_bundle)
python3 overlays/chromium/tools/check_browser.py "$bundle"
```

The browser configuration uses four jobs and releases analysis state during
execution, trading incremental reuse for lower memory use
([Bazel memory guidance](https://bazel.build/advanced/performance/memory)).

On IOPS-limited Linux builders, sandbox directories can use a private RAM filesystem:

```sh
mkdir -p /tmp/chromium-sandboxes
unshare --user --map-root-user --mount --fork sh -c '
  mount -t tmpfs -o size=8g tmpfs /tmp/chromium-sandboxes &&
  exec bazel --batch --output_user_root=/tmp/chromium-ram-bazel build \
    --config=browser --sandbox_base=/tmp/chromium-sandboxes \
    @chromium//native:browser_bundle
'
```

The mount disappears after the batch build. Compiler and generator actions keep
their sandbox isolation; local compilation can select vendored headers before
the BCR forwarding headers.

No local BCR registry required. `build/dependencies.bzl` fetches pinned archives,
applies existing patches, and projects maintained overlay files into each source
repository. Shared Abseil and BoringSSL module overrides preserve ABI consistency
with Protobuf. Source integrity checks remain enabled.

After changing overlay-only targets in Abseil or BoringSSL, regenerate their
small additive module patches:

```sh
python3 tools/update_combined_patches.py
```

Hermeticbuild LLVM (`llvm@0.8.26`) supplies C/C++ toolchains. Chromium's pinned
Rust compiler and Node.js build tools remain unchanged. Native build rules do
not execute GN, Ninja or CMake.

Legacy BCR templates and staging utilities remain available for reference.
They are not required by the combined workspace. No module has been published.

[Compatibility registry](compatibility_registry/README.md) preserves thirteen
independently versioned dependency overlays in one registry. Standalone Chromium
packaging bundles private dependency overlays and provides a browser consumer
presubmit. The staged registry contains 28 modules; browser-bundle analysis
passes against the pinned Chromium archive (379,665 configured targets).
Native browser linking, `--version` and headless HTTP validation pass. Hosted
BCR presubmits have not run; no module has been published.

## License

Overlay scaffolding: BSD-3-Clause. Shared staging tool: Apache-2.0, adapted from
perplexityai/rocksdb. Upstream projects retain their own licenses.
