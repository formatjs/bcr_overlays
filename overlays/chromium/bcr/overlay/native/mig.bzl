"""Declared SDK and host tools for Chromium's Mach interface generators."""

load("@rules_cc//cc:find_cc_toolchain.bzl", "find_cpp_toolchain")
load("@rules_python//python:defs.bzl", "py_binary")
load(":python_action.bzl", "ChromiumFilesInfo")

def _inputs_impl(ctx):
    sdk = ctx.attr._sdk[DefaultInfo].files.to_list()
    if len(sdk) != 1:
        fail("MIG requires one declared SDK directory")
    mappings = [(sdk[0], "third_party/macos_sdk")]
    executables = []
    runfiles = []
    for tool, logical in [
        (ctx.attr.driver, "third_party/mig/bin/mig"),
        (ctx.attr._migcom, "third_party/mig/bin/migcom"),
        (ctx.attr._clang, "third_party/llvm-build/Release+Asserts/bin/clang"),
    ]:
        runner = tool[DefaultInfo].files_to_run
        if runner.executable == None:
            fail("MIG tool must be executable: %s" % tool.label)
        mappings.append((runner.executable, logical))
        executables.append((runner, logical))
        runfiles.append(tool[DefaultInfo].default_runfiles.files)
    return [
        DefaultInfo(files = depset([file for file, _ in mappings], transitive = runfiles + [find_cpp_toolchain(ctx).all_files])),
        ChromiumFilesInfo(mappings = depset(mappings), executables = executables),
    ]

_inputs = rule(
    implementation = _inputs_impl,
    attrs = {
        "driver": attr.label(executable = True, cfg = "exec", mandatory = True),
        "_migcom": attr.label(default = Label("@chromium_mig//:migcom"), executable = True, cfg = "exec", allow_single_file = True),
        "_clang": attr.label(default = Label("@llvm//tools:clang"), executable = True, cfg = "exec", allow_single_file = True),
        "_sdk": attr.label(default = Label("@macos_sdk//sysroot")),
    },
    toolchains = ["@bazel_tools//tools/cpp:toolchain_type"],
    fragments = ["cpp"],
)

def chromium_mig_inputs(name):
    """Stage pinned MIG, Clang and the same SDK used by C++ compilation."""
    py_binary(
        name = name + "_driver",
        srcs = ["mig_driver.py"],
        main = "mig_driver.py",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
    )
    _inputs(name = name, driver = ":" + name + "_driver")
