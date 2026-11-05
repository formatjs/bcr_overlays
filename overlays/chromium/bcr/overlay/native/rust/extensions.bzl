"""Chromium's exact Linux Rust compiler archive, pinned by DEPS SHA-256."""

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

def _compiler_impl(module_ctx):
    http_archive(
        name = "chromium_rust_compiler",
        urls = ["https://commondatastorage.googleapis.com/chromium-browser-clang/Linux_x64/rust-toolchain-15283f6fe95e5b604273d13a428bab5fc0788f5a-1-llvmorg-22-init-8940-g4d4cb757.tar.xz?generation=1758743116775859"],
        sha256 = "2bdaea0b11cb11a8f2f4dcb79b0dbb4bf38e2bd22479ff8014f55b9b6890e135",
        type = "tar.xz",
        build_file = Label(":compiler.BUILD.bazel"),
    )
    return module_ctx.extension_metadata(reproducible = True)

chromium_rust = module_extension(implementation = _compiler_impl)
