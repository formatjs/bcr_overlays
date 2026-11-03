# Dependency overlay audit

Checked 2026-11-03 against the complete BCR module directory
([registry tree](https://api.github.com/repos/bazelbuild/bazel-central-registry/git/trees/b275823006bd7e75f72f41f7bfcd31609076da9e),
1,394 entries). Names and feature coverage below are a first pass, not a complete
Chromium dependency inventory.

## New overlays

No matching BCR modules found for these seven dependencies. Prioritize V8,
Skia and ANGLE, then the remaining browser features. Each overlay needs a
native Bazel implementation; directory scaffolding alone does not supply one.

- [V8](../overlays/v8): JavaScript engine; native Torque and
  snapshot generation need separate host and target configurations.
- [Skia](../overlays/skia): graphics; preserve Chromium's enabled
  backends and model shader generation as declared actions.
- [ANGLE](../overlays/angle): graphics API translation and shader
  compiler. Backend selection must match Chromium's GPU configuration.
- [Dawn](../overlays/dawn): WebGPU; requires generated API bindings
  and platform backend dependencies.
- [WebRTC](../overlays/webrtc): real-time audio/video and data
  channels; align Chromium integration flags and codec dependencies.
- [PDFium](../overlays/pdfium): PDF viewer; align font, image and
  JavaScript dependencies with Chromium's integration.
- [SwiftShader](../overlays/swiftshader): software graphics
  fallback; requires its compiler/backend dependencies.

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
