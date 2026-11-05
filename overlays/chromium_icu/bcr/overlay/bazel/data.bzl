"""Embed Chromium's checked-in ICU data through its native assembly generator."""

def _data_impl(ctx):
    output = ctx.actions.declare_file(ctx.label.name + ".S")
    ctx.actions.run(
        executable = ctx.attr._tool[DefaultInfo].files_to_run,
        arguments = [ctx.file.src.path, output.path],
        inputs = [ctx.file.src],
        outputs = [output],
        mnemonic = "IcuDataAssembly",
    )
    return [DefaultInfo(files = depset([output]))]

icu_data_assembly = rule(
    implementation = _data_impl,
    attrs = {
        "src": attr.label(allow_single_file = [".dat"], mandatory = True),
        "_tool": attr.label(
            default = Label("//:make_data_assembly_tool"),
            executable = True,
            cfg = "exec",
        ),
    },
)
