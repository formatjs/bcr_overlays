# Dawn native Bazel overlay

Status: partial implementation in the combined root workspace. Native API header
generators, procedure/thread dispatch, common support and full captured Tint API
build there. Native OpenGL/Vulkan backend compilation and null-device validation
also pass. Loader, validation and SwiftShader runtime artifacts build. Software
Vulkan compute/raster tests pass. Browser integration and publication remain pending.
The pinned upstream `WORKSPACE.bazel` supports Tint only; it does not provide
Dawn backend targets. The combined build supplies those native rules.

Build/test from repository root:

```sh
bazel test //:dawn_runtime_test //:tint_runtime_test //:dawn_native_runtime_test
```

Upstream: [Dawn](https://dawn.googlesource.com/dawn.git), revision
`cee9cb0d67e749bf42f5e90cb3b8a6f525dbb920`, matching Chromium 142.0.7444.59's DEPS.
Machine-readable pin: [upstream.json](upstream.json).

No BCR release exists. Remaining work goes into the combined root build;
separate registry staging is not required. This directory retains its original
source pin and unpublished scaffold.
Build rules and generators must be native Bazel. Reuse compatible BCR dependencies.
No CMake, GN, Ninja or foreign-build wrappers.
