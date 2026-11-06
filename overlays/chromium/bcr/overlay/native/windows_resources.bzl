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
        inputs = depset([ctx.file.src] + ctx.files.hdrs, transitive = [toolchain.all_files] + [context.headers for context in contexts]),
        outputs = [preprocessed],
        mnemonic = "ChromiumResourcePreprocess",
    )
    assets = []
    asset_sources = []
    include_options = []
    if ctx.attr.assets:
        anchor = ctx.actions.declare_file(ctx.label.name + "_inputs/out/bazel-import/.anchor")
        ctx.actions.write(anchor, "")
        assets.append(anchor)
        include_options = ["/I", anchor.dirname, "/I", paths.join(anchor.dirname, "gen")]
        if ctx.attr.include_root:
            include_options += ["/I", paths.join(anchor.dirname, "../..", ctx.attr.include_root)]
        for target, logical in ctx.attr.assets.items():
            if paths.is_absolute(logical) or ".." in logical.split("/"):
                fail("invalid resource input path: " + logical)
            files = target[DefaultInfo].files.to_list()
            if len(files) != 1:
                fail("resource input must resolve to one file: " + str(target.label))
            staged = ctx.actions.declare_file(ctx.label.name + "_inputs/" + logical)
            ctx.actions.symlink(output = staged, target_file = files[0])
            assets.append(staged)
            asset_sources.append(files[0])
    ctx.actions.run(
        executable = ctx.executable._resource_compiler,
        arguments = ["/no-preprocess", "/X", "/C", "65001"] + include_options + ["/FO", resource.path, preprocessed.path],
        inputs = [preprocessed] + assets + asset_sources,
        outputs = [resource],
        mnemonic = "ChromiumWindowsResource",
    )
    linker = cc_common.create_linker_input(
        owner = ctx.label,
        user_link_flags = depset([resource.path]),
        additional_inputs = depset([resource]),
    )
    return [
        DefaultInfo(files = depset([resource])),
        CcInfo(linking_context = cc_common.create_linking_context(linker_inputs = depset([linker]))),
    ]

chromium_windows_resource = rule(
    implementation = _resource_impl,
    attrs = {
        "src": attr.label(mandatory = True, allow_single_file = [".rc"]),
        "hdrs": attr.label_list(allow_files = True),
        "assets": attr.label_keyed_string_dict(allow_files = True),
        "defines": attr.string_list(),
        "includes": attr.string_list(),
        "include_root": attr.string(),
        "deps": attr.label_list(providers = [CcInfo]),
        "_resource_compiler": attr.label(default = Label("@llvm//tools:llvm-rc"), executable = True, cfg = "exec", allow_single_file = True),
    },
    toolchains = ["@bazel_tools//tools/cpp:toolchain_type"],
    fragments = ["cpp"],
)
