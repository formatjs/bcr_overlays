# V8 native Bazel overlay

V8 **14.2.231.14**, revision `bb294624702efbb17691b642333f06bf5108e600`,
matching Chromium 142.0.7444.59's DEPS. Reuses upstream's native Bazel source
lists, Torque actions, inspector generator, snapshot generator and C++ targets.
No GN, Ninja, CMake or foreign-build wrapper.

Upstream already owns the engine's Bazel build. The overlay adapts dependencies
and integration settings. [Hermeticbuild Node.js](https://github.com/hermeticbuild/nodejs/tree/main/nodejs/private/patches/v8)
uses the same approach. Shared candidates are hermetic LLVM adjustments, ICU
provider selection and Rust Temporal wiring. Node.js-specific flags and source
pins need separate profiles; patches require adaptation across V8 revisions.

Linux x86_64 variants: `noicu/v8` and `icu/v8`. Intl variant uses Chromium
ICU 74.2 fork and embedded locale data. These standalone variants keep upstream
Bazel defaults. The combined Chromium workspace separately builds its captured
browser profile with sandbox, Temporal, Perfetto and external startup data.
Its runtime check passes. The combined Chromium browser also passes version and
headless HTTP JavaScript/Intl checks.

## Build and consumer check

From repository root:

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py --source-registry overlays/dragonbox/bcr \
  --target-registry "$registry" --module dragonbox --version 1.1.3
python3 tools/stage_bcr_entry.py --source-registry overlays/fp16/bcr \
  --target-registry "$registry" --module fp16 --version 0.0.0-20210320-0a92994.bcr.1
python3 tools/stage_bcr_entry.py --source-registry overlays/chromium_icu/bcr \
  --target-registry "$registry" --module chromium_icu --version 74.2.chromium142
python3 tools/stage_bcr_entry.py --source-registry overlays/v8/bcr \
  --target-registry "$registry" --module v8 --version 14.2.231.14
cd overlays/v8/tests/bcr
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build //:smoke_test //:intl_test
bazel build --registry="file://$registry" --registry=https://bcr.bazel.build @v8//:noicu/d8 @v8//:icu/d8
```

Bazel 9.2.0 pinned. Consumer registers `hermeticbuild/hermetic-llvm` through BCR
`llvm@0.8.26` for target libraries and host tools. Published V8 module leaves
compiler selection to its consumer. Generated files run in Bazel sandboxes.

Consumer links `@v8//:noicu/v8`, creates an isolate, runs JavaScript, decimal
round trips, BigInt, half floats, Unicode/Base64 conversion, WebAssembly and
Promise microtasks. Intl consumer additionally checks French number formatting,
NFC normalization and Chromium-patched word boundaries. Snapshot and Torque
generation are part of both variants.

## Dependencies and patches

- BCR Abseil `20250814.0`, matching upstream MODULE.bazel.
- BCR FastFloat `8.2.4`, replacing V8's unmodified 7.0.0 snapshot.
- BCR Highway `1.4.0.bcr.1`, replacing upstream Bazel's 1.2.0 dependency.
- BCR simdutf `7.7.0`, replacing V8's DEPS-managed copy.
- [Dragonbox](../dragonbox) `1.1.3`, exact V8 DEPS pin, absent from BCR.
- [FP16](../fp16) compatibility extension to existing BCR module.
- [Chromium ICU](../chromium_icu) `74.2.chromium142`, exact Chromium fork.
- Upstream's hash-pinned Jinja2/MarkupSafe requirements for inspector bindings.

`bcr/patches/bcr-dependencies.patch` switches dependency targets and vendored
include paths, propagates public visibility through upstream's library aliases,
allows sandboxed inspector generation, handles Clang's deprecated Abseil
attribute spelling, declares the Wasm PGO atomic header and reserves `-latomic`
for GCC. Hermetic LLVM supplies compiler-rt. It preserves engine feature defaults and runtime checks.
These dependency versions still need broader V8/Chromium compatibility tests.

Each module stages and publishes independently. No module published yet.
Maintainers recorded in [bcr/metadata.json](bcr/metadata.json).
