"""Public C++ headers and linking without private repository quote paths."""

load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

def _codec_dependency_impl(ctx):
    dependency = ctx.attr.dependency[CcInfo]
    headers = dependency.compilation_context

    # Keep repository quote paths private; retain public headers and linking.
    return [CcInfo(
        compilation_context = cc_common.create_compilation_context(
            headers = headers.headers,
            includes = headers.includes,
            system_includes = headers.system_includes,
            framework_includes = headers.framework_includes,
            defines = headers.defines,
            local_defines = headers.local_defines,
        ),
        linking_context = dependency.linking_context,
    )]

chromium_public_dependency = rule(
    implementation = _codec_dependency_impl,
    attrs = {"dependency": attr.label(providers = [CcInfo])},
)

def _link_dependency_impl(ctx):
    return [CcInfo(
        compilation_context = cc_common.create_compilation_context(),
        linking_context = ctx.attr.dependency[CcInfo].linking_context,
    )]

chromium_link_dependency = rule(
    implementation = _link_dependency_impl,
    attrs = {"dependency": attr.label(providers = [CcInfo])},
)

def _header_dependency_impl(ctx):
    return [CcInfo(compilation_context = ctx.attr.dependency[CcInfo].compilation_context)]

chromium_header_dependency = rule(
    implementation = _header_dependency_impl,
    attrs = {"dependency": attr.label(providers = [CcInfo])},
)
