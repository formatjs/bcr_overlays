"""Keep Chromium's Protobuf safety configuration on compiler and runtime."""

load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

_DEFINES = ["PROTOBUF_INTERNAL_BOUNDS_CHECK_MODE_ABORT", "GOOGLE_PROTOBUF_NO_RTTI"]

def _protobuf_flags_impl(settings, _attr):
    flags = settings["//command_line_option:cxxopt"]
    additions = ["-D" + define for define in _DEFINES if "-D" + define not in flags]
    return {"//command_line_option:cxxopt": flags + additions}

_protobuf_flags = transition(
    implementation = _protobuf_flags_impl,
    inputs = ["//command_line_option:cxxopt"],
    outputs = ["//command_line_option:cxxopt"],
)

_ALLOWLIST = attr.label(default = "@bazel_tools//tools/allowlists/function_transition_allowlist")

def _protobuf_library_impl(ctx):
    target = ctx.attr.dep[0]
    dependency = target[CcInfo]
    configuration = CcInfo(compilation_context = cc_common.create_compilation_context(
        defines = depset(_DEFINES),
    ))
    return [
        cc_common.merge_cc_infos(cc_infos = [dependency, configuration]),
        target[DefaultInfo],
    ]

chromium_protobuf_library = rule(
    implementation = _protobuf_library_impl,
    attrs = {
        "dep": attr.label(cfg = _protobuf_flags, providers = [CcInfo], mandatory = True),
        "_allowlist_function_transition": _ALLOWLIST,
    },
)

def _protoc_impl(ctx):
    dependency = ctx.attr.tool[0][DefaultInfo]
    executable = ctx.actions.declare_file(ctx.label.name + ".bin")
    ctx.actions.symlink(
        output = executable,
        target_file = dependency.files_to_run.executable,
        is_executable = True,
    )
    runfiles = ctx.runfiles(files = [dependency.files_to_run.executable]).merge(dependency.default_runfiles)
    return [DefaultInfo(executable = executable, runfiles = runfiles)]

chromium_protoc = rule(
    implementation = _protoc_impl,
    executable = True,
    attrs = {
        "tool": attr.label(cfg = _protobuf_flags, executable = True, mandatory = True),
        "_allowlist_function_transition": _ALLOWLIST,
    },
)
