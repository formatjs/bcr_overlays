"""Browser target platforms; host generators retain their execution platform."""

load("@with_cfg.bzl", "with_cfg")

msvc_static_crt, _msvc_static_crt = with_cfg(native.filegroup).set(
    "features",
    ["static_link_msvcrt", "-dynamic_link_msvcrt"],
).build()

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
).set("macos_minimum_os", "12.0").build()

windows_amd64_browser, _windows_amd64_browser = with_cfg(native.filegroup).set(
    "platforms",
    [Label("@llvm//platforms:windows_x86_64_msvc")],
).set("features", ["static_link_msvcrt", "-dynamic_link_msvcrt"]).build()

windows_arm64_browser, _windows_arm64_browser = with_cfg(native.filegroup).set(
    "platforms",
    [Label("@llvm//platforms:windows_aarch64_msvc")],
).set("features", ["static_link_msvcrt", "-dynamic_link_msvcrt"]).build()
