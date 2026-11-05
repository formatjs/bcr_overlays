"""Run original Python/Node CLI plugins with their declared source layout."""

load(":python_action.bzl", "ChromiumFilesInfo")

_BOOTSTRAP = str(Label("@rules_python//python/config_settings:bootstrap_impl"))

def _script_bootstrap_impl(_settings, _attr):
    return {_BOOTSTRAP: "script"}

_script_bootstrap = transition(
    implementation = _script_bootstrap_impl,
    inputs = [],
    outputs = [_BOOTSTRAP],
)

def _node_python_tool_impl(ctx):
    script = ctx.file.script
    prefix = script.short_path.split("/")[1] if script.short_path.startswith("../") else ctx.workspace_name
    symlinks = {
        prefix + "/third_party/node/linux/node-linux-x64/bin/node": ctx.file.node,
    }
    for file, logical in ctx.attr.packages[ChromiumFilesInfo].mappings.to_list():
        symlinks[prefix + "/" + logical] = file
    tool = ctx.attr.tool[0][DefaultInfo]
    executable = ctx.actions.declare_file(ctx.label.name + ".bin")
    ctx.actions.expand_template(
        template = tool.files_to_run.executable,
        output = executable,
        substitutions = {},
        is_executable = True,
    )
    return [DefaultInfo(
        executable = executable,
        runfiles = tool.default_runfiles.merge(ctx.runfiles(root_symlinks = symlinks)),
    )]

chromium_node_python_tool = rule(
    implementation = _node_python_tool_impl,
    executable = True,
    attrs = {
        "tool": attr.label(executable = True, cfg = _script_bootstrap, mandatory = True),
        "script": attr.label(allow_single_file = True, mandatory = True),
        "node": attr.label(allow_single_file = True, cfg = "exec", mandatory = True),
        "packages": attr.label(providers = [ChromiumFilesInfo], cfg = "exec", mandatory = True),
        "_allowlist_function_transition": attr.label(default = "@bazel_tools//tools/allowlists/function_transition_allowlist"),
    },
)
