"""Browser target platforms; host generators retain their execution platform."""

load("@with_cfg.bzl", "with_cfg")

linux_amd64_browser, _linux_amd64_browser = with_cfg(native.filegroup).set(
    "platforms",
    [Label("@llvm//platforms:linux_x86_64_gnu.2.31")],
).build()

linux_arm64_browser, _linux_arm64_browser = with_cfg(native.filegroup).set(
    "platforms",
    [Label("@llvm//platforms:linux_aarch64_gnu.2.31")],
).build()

darwin_arm64_browser, _darwin_arm64_browser = with_cfg(native.filegroup).set(
    "platforms",
    [Label("@llvm//platforms:macos_aarch64")],
).build()

windows_amd64_browser, _windows_amd64_browser = with_cfg(native.filegroup).set(
    "platforms",
    [Label("@llvm//platforms:windows_x86_64_msvc")],
).build()

windows_arm64_browser, _windows_arm64_browser = with_cfg(native.filegroup).set(
    "platforms",
    [Label("@llvm//platforms:windows_aarch64_msvc")],
).build()
