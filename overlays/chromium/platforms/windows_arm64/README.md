# Windows ARM64

MSVC ABI with hermeticbuild LLVM and libc++. PartitionAlloc's 66 C++ sources
compile and pass native Windows ARM64 heap smoke. The captured Windows base,
Rust, ICU, and tracing profiles are imported; base executable validation is in
progress.

`//tools/ci:base-windows-arm64` exercises Rust JSON parsing, Unicode, temporary
files, and threads. `with_cfg` selects static MSVC CRT globally. Captured Rust
flags retain `-Ctarget-feature=+crt-static`; host tools use Linux support code.
The SDK and ATL payloads match the AMD64 profile.

Regenerate metadata without touching the Linux overlay:

```sh
python3 overlays/chromium/tools/import_windows_base.py \
  --variant windows_arm64 --source-root /path/to/pinned/chromium
buildifier -r overlays/chromium/platforms/windows_arm64/overlay
```

Platform rule adapters remain maintained separately from generated metadata.
Full browser translation and packaging remain pending.
