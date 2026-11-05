"""Expose native host tools and runfiles to Chromium generator actions."""

load(":python_action.bzl", "ChromiumFilesInfo")

def _tool_inputs_impl(ctx):
    runner = ctx.attr.tool[DefaultInfo].files_to_run
    executable = runner.executable
    mappings = [(executable, ctx.attr.logical_path)]
    stage_runtime = ctx.attr.stage_runtime or bool(ctx.attr.runtime_data)
    if stage_runtime:
        directory = ctx.attr.logical_path.rsplit("/", 1)[0]

        # Preserve native loader paths when the executable must move beside data.
        for file in ctx.attr.tool[DefaultInfo].default_runfiles.files.to_list():
            if file == executable:
                continue
            path = file.short_path
            runfile = path[3:] if path.startswith("../") else ctx.workspace_name + "/" + path
            mappings.append((file, directory + "/" + executable.basename + ".runfiles/" + runfile))
            if ctx.attr.stage_runtime and file.path.startswith(executable.dirname + "/"):
                relative = file.path[len(executable.dirname) + 1:]
                mappings.append((file, directory + "/" + relative))
        for target, relative in ctx.attr.runtime_data.items():
            files = target[DefaultInfo].files.to_list()
            if len(files) != 1:
                fail("runtime data must identify one file: %s" % target.label)
            mappings.append((files[0], directory + "/" + relative))
    return [
        DefaultInfo(files = depset([file for file, _ in mappings])),
        ChromiumFilesInfo(
            mappings = depset(mappings),
            executables = [(runner, ctx.attr.logical_path)],
            copied_executables = depset([ctx.attr.logical_path] if stage_runtime else []),
        ),
    ]

chromium_tool_inputs = rule(
    implementation = _tool_inputs_impl,
    attrs = {
        "tool": attr.label(executable = True, cfg = "exec", mandatory = True),
        "logical_path": attr.string(mandatory = True),
        "runtime_data": attr.label_keyed_string_dict(allow_files = True, cfg = "exec"),
        "stage_runtime": attr.bool(default = False),
    },
)
