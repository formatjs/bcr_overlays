# macOS ARM64

The captured browser graph contains 18,863 targets. Extraction uses pinned
hermeticbuild LLVM and Apple's pinned SDK; no host Xcode discovery runs.
`capture/inputs.json` records SDK provenance and extraction patches.

PartitionAlloc's 69 C++ and five Objective-C++ sources use the captured platform
settings. Objective-C++ compilation uses the registered C++ toolchain through
`cc_common`; per-target ARC flags are preserved. The SDK includes Chromium's
frameworks, their symlink dependencies, and relocated Cryptex frameworks.

`//tools/ci:allocator-darwin-arm64` cross-links a heap smoke executable on Linux.
CI hands it to a native macOS ARM64 runner. `with_cfg` selects the target platform
and macOS 12 deployment target for compiler, runtime, and linker consistency.
Full browser translation and app bundle packaging remain pending.

To recapture, apply `capture/mac_sdk_cross.patch` to the pinned Chromium checkout,
materialize the source revisions in `capture/inputs.json`, and configure
`target_os="mac"`, `target_cpu="arm64"`, `use_system_xcode=false`,
`clang_use_chrome_plugins=false`, `mac_sdk_path`, and `mac_llvm_bin_path`.
Generate the complete GN IDE JSON before selecting the browser dependency closure;
IDE filters omit required data dependencies. Pass the SDK root through
`tools/capture_native_graph.py --path-map 'SDK_PATH=$MACOS_SDK_ROOT'` and pass
`--extraction-inputs overlays/chromium/platforms/darwin_arm64/capture/inputs.json`.
