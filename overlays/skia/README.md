# Skia native Bazel overlay

Native Linux x86_64 raster core and path operations. Pinned to Chromium
142.0.7444.59's Skia revision `f4ed99d2443962782cf5f8b4dd27179f131e7cbe`.
Proposed module version `142.0.0` identifies this milestone snapshot.

Public targets: `@skia//:core`, `@skia//:pathops`. Reuses upstream's explicit
native Bazel source lists, SkSL sources, architecture dispatch and skcms.
Keeps upstream configuration inside `include/config`; no separate configuration
module or upstream development toolchain is needed.

GPU backends, codecs, fonts, Rust components and Chromium's integration flags
remain pending. Public root exposes only the two implemented targets.
No GN, Ninja, CMake or foreign-build backend.

## Build and validate

From repository root:

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py --source-registry overlays/skia/bcr \
  --target-registry "$registry" --module skia --version 142.0.0
cd overlays/skia/tests/bcr
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build //:smoke_test
```

Consumer pins Bazel 9.2.0, registers hermeticbuild LLVM `llvm@0.8.26`, links
statically to match Skia's hidden-symbol configuration. Test checks actual raster
pixels and overlapping path intersection. BCR test module uses the same test
and toolchain. Published library leaves compiler selection to its consumer.

Patch keeps configuration headers declared through Bazel's virtual includes,
replaces external configuration labels with local labels and retains upstream
compiler warnings without `-Werror`. LLVM 23 emits new lifetime-annotation
warnings on this older source baseline; runtime checks remain unchanged.
No runtime, graphics or safety feature is disabled to make the tests pass.

Skia stages and publishes independently. Nothing published to BCR yet;
maintainers recorded in [bcr/metadata.json](bcr/metadata.json).
