"""Fail explicitly for rustdoc, which Chromium's compiler archive omits."""

def _unsupported_impl(ctx):
    output = ctx.actions.declare_file(ctx.label.name + ".sh")
    ctx.actions.write(
        output,
        "#!/bin/sh\nprintf '%s\\n' 'Chromium compiler archive does not distribute rustdoc.' >&2\nexit 1\n",
        is_executable = True,
    )
    return [DefaultInfo(executable = output)]

unsupported_rustdoc = rule(implementation = _unsupported_impl, executable = True)
