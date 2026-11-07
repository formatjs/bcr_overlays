# Windows ARM64

MSVC ABI with hermeticbuild LLVM and libc++. PartitionAlloc's 66 C++ sources
compile and pass native Windows ARM64 heap smoke. The captured Windows base,
Rust, ICU, and tracing profiles pass native browser smoke.

`//tools/ci:base-windows-arm64` exercises Rust JSON parsing, Unicode, temporary
files, and threads. `with_cfg` selects static MSVC CRT globally. Captured Rust
flags retain `-Ctarget-feature=+crt-static`; host tools use Linux support code.
The SDK and ATL payloads match the AMD64 profile.

GPU command services and the media closure cross-build on Linux with the MSVC
ABI and static CRT. The media build includes FFmpeg, native codecs, storage,
and Media Foundation decoders. Full browser artifacts cross-build on Linux.

Regenerate metadata without touching the Linux overlay:

```sh
python3 overlays/chromium/tools/import_windows_base.py \
  --variant windows_arm64 --source-root /path/to/pinned/chromium
buildifier -r overlays/chromium/platforms/windows_arm64/overlay
```

Platform rule adapters remain maintained separately from generated metadata.
Native rendering smoke remains under validation.

Linux captures apply [the V8 snapshot patch](capture/v8_snapshot_cross.patch)
so the host generator uses the ARM64 simulator with the native Windows return-address ABI.
Capture rejects architecture or signing mismatches between generator and runtime.
Patch hashes live in [capture provenance](capture/inputs.json).
