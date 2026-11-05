# Linux ARM64 overlay

This overlay layers ARM64 metadata over the shared Chromium source archive.
Host generators use AMD64 dependencies; V8 snapshot generators retain their
ARM64 target settings. Runtime libraries and SDK headers select the target CPU.

Validated from Linux AMD64 with `--config=browser` and
`--platforms=@llvm//platforms:linux_aarch64_gnu.2.31`:

- `@chromium_linux_arm64//native:browser_assets`
- ARM64 PartitionAlloc, including MTE compiler features
- ARM64 NSS/NSPR libraries, runtime consumers, and module checksums

Full browser analysis passes. `//tools/ci:linux-arm64` uses this overlay for
cross-compilation on AMD64. ARM64 binaries have not been executed; full browser
compilation, packaging, and native rendering smoke remain pending.
