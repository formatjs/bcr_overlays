"""Declared NSS header exports and native generator actions."""

def _export_headers_impl(ctx):
    outputs = []
    for source, destination in ctx.attr.layout.items():
        output = ctx.actions.declare_file("include/" + destination)
        ctx.actions.symlink(output = output, target_file = source[DefaultInfo].files.to_list()[0])
        outputs.append(output)
    return [DefaultInfo(files = depset(outputs))]

export_headers = rule(
    implementation = _export_headers_impl,
    attrs = {"layout": attr.label_keyed_string_dict(allow_files = True)},
)

def _generate_impl(ctx):
    ctx.actions.run(
        executable = ctx.executable.tool,
        arguments = [ctx.file.source.path, ctx.outputs.out.path],
        inputs = [ctx.file.source],
        outputs = [ctx.outputs.out],
        tools = [ctx.attr.tool[DefaultInfo].files_to_run],
        mnemonic = "NssGenerate",
    )
    return [DefaultInfo(files = depset([ctx.outputs.out]))]

generate = rule(
    implementation = _generate_impl,
    attrs = {
        "tool": attr.label(executable = True, cfg = "exec", mandatory = True),
        "source": attr.label(allow_single_file = True, mandatory = True),
        "out": attr.output(mandatory = True),
    },
)

def _sign_impl(ctx):
    ctx.actions.run(
        executable = ctx.executable._driver,
        arguments = [ctx.executable.tool.path, ctx.file.library.path, ctx.outputs.out.path],
        inputs = [ctx.file.library],
        outputs = [ctx.outputs.out],
        tools = [ctx.attr.tool[DefaultInfo].files_to_run, ctx.attr._driver[DefaultInfo].files_to_run],
        mnemonic = "NssModuleSign",
    )
    return [DefaultInfo(files = depset([ctx.outputs.out]))]

sign_module = rule(
    implementation = _sign_impl,
    attrs = {
        "_driver": attr.label(default = "//bazel:sign_driver", executable = True, cfg = "exec"),
        "tool": attr.label(executable = True, cfg = "exec", mandatory = True),
        "library": attr.label(allow_single_file = True, mandatory = True),
        "out": attr.output(mandatory = True),
    },
)
