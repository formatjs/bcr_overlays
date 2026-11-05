# SwiftShader native Bazel overlay

Implemented in the combined root workspace. Pinned Subzero/Marl, native assembly,
BCR SPIR-V tools and native Wayland/FFI build with hermetic LLVM. Real software
Vulkan compute and raster readbacks pass through Dawn with validation loaded.
The original Python action generates the Linux ICD manifest beside the driver;
the runtime test loads that manifest without rewriting its relative library path.

```sh
bazel build @chromium//native:swiftshader_runtime
bazel test @chromium//native:swiftshader_runtime_test //:wayland_runtime_test
```

Upstream revision `5f1c459a11bb4899301e89609cbf7547f9f31e20` matches Chromium
142.0.7444.59. [upstream.json](upstream.json) records the pin. Rules/source lists
live in [Chromium's native directory](../chromium/bcr/overlay/native/swiftshader.bzl).

Standalone module packaging/publication remains planned. The empty version list
prevents publishing the scaffold. Browser assembly remains unfinished.
