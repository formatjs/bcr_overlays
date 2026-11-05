"""Expose native host tools and runfiles to Chromium generator actions."""

load(":python_action.bzl", "ChromiumFilesInfo")

def _tool_inputs_impl(ctx):
    runner = ctx.attr.tool[DefaultInfo].files_to_run
    executable = runner.executable
    return [
        DefaultInfo(files = depset([executable])),
        ChromiumFilesInfo(
            mappings = depset([(executable, ctx.attr.logical_path)]),
            executables = [(runner, ctx.attr.logical_path)],
        ),
    ]

chromium_tool_inputs = rule(
    implementation = _tool_inputs_impl,
    attrs = {
        "tool": attr.label(executable = True, cfg = "exec", mandatory = True),
        "logical_path": attr.string(mandatory = True),
    },
)
