"""Compile Windows resources with declared LLVM tools and MSVC SDK inputs."""

load("@bazel_skylib//lib:paths.bzl", "paths")
load("@rules_cc//cc:action_names.bzl", "ACTION_NAMES")
load("@rules_cc//cc:find_cc_toolchain.bzl", "find_cpp_toolchain")
load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

def _resource_impl(ctx):
    toolchain = find_cpp_toolchain(ctx)
    features = cc_common.configure_features(
        ctx = ctx,
        cc_toolchain = toolchain,
        requested_features = ctx.features,
        unsupported_features = ctx.disabled_features,
    )
    contexts = [dependency[CcInfo].compilation_context for dependency in ctx.attr.deps]
    preprocessed = ctx.actions.declare_file(ctx.label.name + ".rc.i")
    resource = ctx.actions.declare_file(ctx.label.name + ".res")
    output = ctx.actions.declare_file(ctx.label.name + ".obj")
    root = paths.join(ctx.label.workspace_root, ctx.label.package)
    variables = cc_common.create_compile_variables(
        cc_toolchain = toolchain,
        feature_configuration = features,
        source_file = ctx.file.src.path,
        output_file = preprocessed.path,
        user_compile_flags = ["/clang:-E", "/clang:-P", "/TC", "/clang:-o", "/clang:" + preprocessed.path],
        include_directories = depset([paths.normalize(paths.join(root, path)) for path in ctx.attr.includes], transitive = [context.includes for context in contexts]),
        quote_include_directories = depset(transitive = [context.quote_includes for context in contexts]),
        system_include_directories = depset(transitive = [context.system_includes for context in contexts]),
        preprocessor_defines = depset(ctx.attr.defines + ["RC_INVOKED"], transitive = [context.defines for context in contexts]),
    )
    ctx.actions.run(
        executable = cc_common.get_tool_for_action(feature_configuration = features, action_name = ACTION_NAMES.c_compile),
        arguments = cc_common.get_memory_inefficient_command_line(feature_configuration = features, action_name = ACTION_NAMES.c_compile, variables = variables),
        env = cc_common.get_environment_variables(feature_configuration = features, action_name = ACTION_NAMES.c_compile, variables = variables),
        inputs = depset([ctx.file.src], transitive = [toolchain.all_files] + [context.headers for context in contexts]),
        outputs = [preprocessed],
        mnemonic = "ChromiumResourcePreprocess",
    )
    ctx.actions.run(
        executable = ctx.executable._resource_compiler,
        arguments = ["/no-preprocess", "/X", "/FO", resource.path, preprocessed.path],
        inputs = [preprocessed],
        outputs = [resource],
        mnemonic = "ChromiumWindowsResource",
    )
    machine = "aarch64" if ctx.target_platform_has_constraint(ctx.attr._arm64[platform_common.ConstraintValueInfo]) else "x86_64"
    ctx.actions.run(
        executable = ctx.executable._coff_converter,
        arguments = ["--input-format=res", "--output-format=coff", "--target=" + machine, "--input=" + resource.path, "--output=" + output.path],
        inputs = [resource],
        outputs = [output],
        mnemonic = "ChromiumResourceCoff",
    )
    return [DefaultInfo(files = depset([output]))]

chromium_windows_resource = rule(
    implementation = _resource_impl,
    attrs = {
        "src": attr.label(mandatory = True, allow_single_file = [".rc"]),
        "defines": attr.string_list(),
        "includes": attr.string_list(),
        "deps": attr.label_list(providers = [CcInfo]),
        "_arm64": attr.label(default = Label("@platforms//cpu:aarch64")),
        "_coff_converter": attr.label(default = Label("@llvm//tools:llvm-windres"), executable = True, cfg = "exec", allow_single_file = True),
        "_resource_compiler": attr.label(default = Label("@llvm//tools:llvm-rc"), executable = True, cfg = "exec", allow_single_file = True),
    },
    toolchains = ["@bazel_tools//tools/cpp:toolchain_type"],
    fragments = ["cpp"],
)
