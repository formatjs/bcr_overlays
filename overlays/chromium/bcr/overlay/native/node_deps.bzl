"""Fetch Chromium's exact prepatched WebUI sources; installers never execute."""

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")
load(":npm_packages.bzl", "NODE_MODULES_ARCHIVE")

_BUILD = """package(default_visibility = ["//visibility:public"])
exports_files(glob(["node_modules/**"]))
filegroup(
    name = "files",
    srcs = glob(["node_modules/**"]),
)
"""

def _npm_sources_impl(ctx):
    http_archive(
        name = "chromium_node_modules",
        urls = [NODE_MODULES_ARCHIVE["url"]],
        sha256 = NODE_MODULES_ARCHIVE["sha256"],
        type = "tar.gz",
        add_prefix = "node_modules",
        build_file_content = _BUILD,
    )
    return ctx.extension_metadata(reproducible = True)

npm_sources = module_extension(implementation = _npm_sources_impl)
