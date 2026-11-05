"""Apply Chromium dependency settings without changing consumer-global flags."""

load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

def _flags_impl(settings, attr):
    flags = settings["//command_line_option:cxxopt"]
    additions = ["-D" + value for value in attr.defines if "-D" + value not in flags]
    return {"//command_line_option:cxxopt": flags + additions}

_flags = transition(implementation = _flags_impl, inputs = ["//command_line_option:cxxopt"], outputs = ["//command_line_option:cxxopt"])

def _library_impl(ctx):
    dependency = ctx.attr.dep[0]
    defines = CcInfo(compilation_context = cc_common.create_compilation_context(defines = depset(ctx.attr.defines)))
    return [cc_common.merge_cc_infos(cc_infos = [dependency[CcInfo], defines]), dependency[DefaultInfo]]

configured_cc_library = rule(
    implementation = _library_impl,
    attrs = {
        "dep": attr.label(cfg = _flags, providers = [CcInfo], mandatory = True),
        "defines": attr.string_list(mandatory = True),
        "_allowlist_function_transition": attr.label(default = "@bazel_tools//tools/allowlists/function_transition_allowlist"),
    },
)
