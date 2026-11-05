"""Keep Qt on the captured SDK's GNU C++ headers and runtime."""

load("@rules_cc//cc:find_cc_toolchain.bzl", "find_cpp_toolchain", "use_cc_toolchain")
load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

def _qt_sdk_headers_impl(ctx):
    toolchain = find_cpp_toolchain(ctx)
    resources = [file for file in toolchain.all_files.to_list() if "/lib/clang/" in file.path and "/" not in file.path.split("/lib/clang/", 1)[1]]
    if len(resources) != 1:
        fail("Qt SDK profile needs one Clang resource directory from the selected toolchain")
    root = ctx.attr.sdk.label.workspace_root
    headers = ctx.attr.sdk[CcInfo].compilation_context.headers
    return [CcInfo(
        compilation_context = cc_common.create_compilation_context(
            headers = headers,
            includes = depset([
                root + "/usr/include/c++/10",
                root + "/usr/include/x86_64-linux-gnu/c++/10",
                resources[0].path + "/include",
                root + "/usr/include/x86_64-linux-gnu",
                root + "/usr/include",
            ], order = "preorder"),
        ),
        linking_context = ctx.attr.sdk[CcInfo].linking_context,
    )]

chromium_qt_sdk_headers = rule(
    implementation = _qt_sdk_headers_impl,
    attrs = {"sdk": attr.label(mandatory = True, providers = [CcInfo])},
    fragments = ["cpp"],
    toolchains = use_cc_toolchain(),
)
