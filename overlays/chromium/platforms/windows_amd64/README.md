# Windows AMD64

MSVC ABI with hermeticbuild LLVM and libc++. PartitionAlloc's 66 C++ sources
compile and pass native Windows heap smoke. Chromium's base library also
cross-compiles with its captured Windows source, Rust, ICU, and tracing profiles.

`//tools/ci:base-windows-amd64` links a smoke executable for Rust JSON parsing,
Unicode, temporary files, and threads. Native execution validation is in progress.
`with_cfg` selects static MSVC CRT globally; captured Rust flags retain
`-Ctarget-feature=+crt-static`. Host tools use the Linux support libraries.

LLVM's MSVC profile includes the pinned runtime's `delayimp.h` and `delayimp.lib`.
ATL headers come from the matching 14.50.35717 Visual Studio payload, pinned by
SHA-256 in `build/msvc_atl.bzl`. Download uses the existing MSVC license flag.

Regenerate metadata without touching the Linux overlay:

```sh
python3 overlays/chromium/tools/import_windows_base.py \
  --variant windows_amd64 --source-root /path/to/pinned/chromium
buildifier -r overlays/chromium/platforms/windows_amd64/overlay
```

Platform rule adapters remain maintained separately from generated metadata.
Full browser translation and packaging remain pending.
