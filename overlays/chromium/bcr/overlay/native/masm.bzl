"""Assemble Chromium's MSVC sources with hermetic LLVM."""

def _masm_impl(ctx):
    output = ctx.actions.declare_file(ctx.label.name + ".obj")
    arguments = ctx.actions.args()
    arguments.add_all(["--m64", "/nologo", "/c"])
    arguments.add("/Fo" + output.path)
    arguments.add(ctx.file.src)
    ctx.actions.run(
        executable = ctx.executable._assembler,
        arguments = [arguments],
        inputs = [ctx.file.src],
        outputs = [output],
        mnemonic = "ChromiumMasm",
    )
    return [DefaultInfo(files = depset([output]))]

chromium_masm = rule(
    implementation = _masm_impl,
    attrs = {
        "src": attr.label(mandatory = True, allow_single_file = [".asm"]),
        "_assembler": attr.label(
            default = Label("@llvm//tools:llvm-ml"),
            executable = True,
            cfg = "exec",
            allow_single_file = True,
        ),
    },
)
