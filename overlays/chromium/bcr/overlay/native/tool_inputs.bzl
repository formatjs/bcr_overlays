"""Expose native host tools and private runtimes to Chromium generators."""

load(":python_action.bzl", "ChromiumFilesInfo")

def _stage_runtime(ctx, executable):
    sources = {executable.basename: executable}
    for file in ctx.attr.tool[DefaultInfo].default_runfiles.files.to_list():
        if file == executable:
            continue
        path = file.short_path
        runfile = path[3:] if path.startswith("../") else ctx.workspace_name + "/" + path
        sources[executable.basename + ".runfiles/" + runfile] = file
        if ctx.attr.stage_runtime and file.path.startswith(executable.dirname + "/"):
            sources[file.path[len(executable.dirname) + 1:]] = file
    for target, relative in ctx.attr.runtime_data.items():
        if relative.startswith("/") or ".." in relative.split("/") or not relative:
            fail("invalid runtime data path: %s" % relative)
        files = target[DefaultInfo].files.to_list()
        if len(files) != 1:
            fail("runtime data must identify one file: %s" % target.label)
        if relative in sources and sources[relative] != files[0]:
            fail("conflicting runtime data: %s" % relative)
        sources[relative] = files[0]
    outputs = {relative: ctx.actions.declare_file(ctx.label.name + ".runtime/" + relative) for relative in sorted(sources)}
    manifest = ctx.actions.declare_file(ctx.label.name + ".runtime.json")
    ctx.actions.write(manifest, json.encode([[sources[path].path, outputs[path].path] for path in sorted(sources)]))
    python = ctx.attr._python[platform_common.ToolchainInfo].py3_runtime
    ctx.actions.run(
        executable = python.interpreter,
        arguments = ["-I", "-B", ctx.file._stage_script.path, manifest.path],
        inputs = depset(sources.values() + [manifest, ctx.file._stage_script], transitive = [python.files]),
        outputs = outputs.values(),
        mnemonic = "ChromiumToolRuntime",
    )
    return outputs[executable.basename], outputs.values()

def _tool_inputs_impl(ctx):
    runner = ctx.attr.tool[DefaultInfo].files_to_run
    executable = runner.executable
    files = [executable]
    if ctx.attr.stage_runtime or ctx.attr.runtime_data:
        # Keep host runtime data beside its executable, outside target GN inputs.
        executable, files = _stage_runtime(ctx, executable)
    return [
        DefaultInfo(files = depset(files)),
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
        "runtime_data": attr.label_keyed_string_dict(allow_files = True, cfg = "exec"),
        "stage_runtime": attr.bool(default = False),
        "_stage_script": attr.label(default = Label("//native:stage_tool.py"), allow_single_file = True),
        "_python": attr.label(default = Label("@rules_python//python:current_py_toolchain"), cfg = "exec"),
    },
)
