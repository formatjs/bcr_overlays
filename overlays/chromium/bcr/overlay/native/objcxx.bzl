"""Compile Objective-C++ with the registered hermetic C++ toolchain."""

load("@rules_cc//cc:find_cc_toolchain.bzl", "find_cpp_toolchain")
load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

def _tokenized_defines(ctx, values):
    result = []
    for value in values:
        tokens = ctx.tokenize(ctx.expand_make_variables("defines", value, {}))
        if len(tokens) != 1:
            fail("define must expand to one token: %s" % value)
        result.append(tokens[0])
    return result

def _objcxx_library_impl(ctx):
    toolchain = find_cpp_toolchain(ctx)
    features = cc_common.configure_features(
        ctx = ctx,
        cc_toolchain = toolchain,
        requested_features = ctx.features,
        unsupported_features = ctx.disabled_features,
    )
    compilation_context, outputs = cc_common.compile(
        actions = ctx.actions,
        feature_configuration = features,
        cc_toolchain = toolchain,
        name = ctx.label.name,
        language = "objc++",
        srcs = ctx.files.srcs,
        public_hdrs = ctx.files.hdrs,
        compilation_contexts = [dep[CcInfo].compilation_context for dep in ctx.attr.deps],
        user_compile_flags = ctx.attr.copts,
        defines = _tokenized_defines(ctx, ctx.attr.defines),
        local_defines = _tokenized_defines(ctx, ctx.attr.local_defines),
    )
    linking_context, linking_outputs = cc_common.create_linking_context_from_compilation_outputs(
        actions = ctx.actions,
        name = ctx.label.name,
        feature_configuration = features,
        cc_toolchain = toolchain,
        compilation_outputs = outputs,
        linking_contexts = [dep[CcInfo].linking_context for dep in ctx.attr.deps],
        disallow_dynamic_library = True,
        alwayslink = ctx.attr.alwayslink,
        user_link_flags = ctx.attr.linkopts,
    )
    library = linking_outputs.library_to_link
    return [
        CcInfo(compilation_context = compilation_context, linking_context = linking_context),
        DefaultInfo(files = depset([file for file in [library.static_library, library.pic_static_library] if file])),
    ]

objcxx_library = rule(
    implementation = _objcxx_library_impl,
    attrs = {
        "alwayslink": attr.bool(),
        "srcs": attr.label_list(allow_files = [".mm", ".m"]),
        "hdrs": attr.label_list(allow_files = True),
        "deps": attr.label_list(providers = [CcInfo]),
        "copts": attr.string_list(),
        "defines": attr.string_list(),
        "local_defines": attr.string_list(),
        "linkopts": attr.string_list(),
    },
    fragments = ["cpp"],
    toolchains = ["@bazel_tools//tools/cpp:toolchain_type"],
)
