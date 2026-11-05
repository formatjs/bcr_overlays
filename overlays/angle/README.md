# ANGLE native Bazel overlay

Native Linux x86_64 shader compiler, pinned to Chromium 142.0.7444.59's revision
`e5b338502c7c65bd38d4695bc557938ca4cc3aa7`. Proposed module version:
`2.1.0-e5b338502c7c`.

Public target: `@angle//:translator`. Includes WebGL/GLES shader validation,
ESSL output, desktop GLSL output, preprocessing, common utilities and BCR Abseil.
The combined root workspace also builds the full captured EGL/GLES runtime,
including GL, Vulkan, null and Dawn backends. Its software-Vulkan test compiles
and links GLSL, draws a triangle, verifies every pixel and rejects invalid GLSL.
Standalone registry packaging still exposes the translator profile above.

```sh
bazel build @chromium//native:angle_runtime
bazel test @chromium//native:angle_runtime_test
```
No GN, Ninja, CMake or foreign-build wrapper runs during a build.

## Build and validate

From repository root:

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py --source-registry overlays/angle/bcr \
  --target-registry "$registry" --module angle --version 2.1.0-e5b338502c7c
cd overlays/angle/tests/bcr
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build //:smoke_test
```

Consumer pins Bazel 9.2.0 and hermeticbuild LLVM `llvm@0.8.26`. Test translates
valid WebGL2 fragment shaders to ESSL and GLSL, rejects invalid shaders with
actual diagnostics, checks generated archive commit metadata. BCR test module
uses the same source and toolchain. Published library leaves compiler choice
to its consumer. Runtime validation and assertions retain upstream defaults.

## Source lists and generated headers

`bcr/overlay/angle_sources.bzl` imports explicit upstream source lists from
`src/compiler.gni` and `src/libGLESv2.gni`. Regenerate outside the build:

```sh
python3 overlays/angle/tools/import_sources.py /path/to/pinned/angle/source
```

Importer selects Linux platform sources and ESSL/GLSL backends, checks every
listed file exists. It parses literal lists; it does not invoke GN.

Native `angle_versions` rule writes archive metadata using the pinned commit,
matching upstream's gitless archive behavior: unknown date, commit position 0.
No Git checkout or undeclared Git command is needed. Shader-program version
header runs upstream's source-content hashing script through a declared Python
tool. Inputs include selected sources, headers and Bazel configuration, so this
cache namespace deliberately differs from GN builds.

ANGLE stages and publishes independently. Nothing published to BCR yet;
maintainers recorded in [bcr/metadata.json](bcr/metadata.json).
