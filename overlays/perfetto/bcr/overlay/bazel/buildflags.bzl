"""Generate Perfetto's original Chromium runtime flags with upstream Python."""

load(":chromium_flags.bzl", "CHROMIUM_FLAGS")

def _flags_impl(ctx):
    response = ctx.actions.declare_file(ctx.label.name + ".rsp")
    output = ctx.actions.declare_file("chromium_config/perfetto_build_flags.h")
    ctx.actions.write(response, "--flags " + " ".join([json.encode(flag) for flag in ctx.attr.flags]))
    ctx.actions.run(
        executable = ctx.attr._tool[DefaultInfo].files_to_run,
        inputs = [response],
        outputs = [output],
        arguments = ["--rsp", response.path, "--out", output.path],
        mnemonic = "PerfettoBuildflags",
    )
    return [DefaultInfo(files = depset([output]))]

_chromium_buildflags = rule(
    implementation = _flags_impl,
    attrs = {
        "flags": attr.string_list(mandatory = True),
        "_tool": attr.label(default = Label("//:write_buildflag_header"), executable = True, cfg = "exec"),
    },
)

def chromium_buildflags(name, **kwargs):
    _chromium_buildflags(name = name, flags = CHROMIUM_FLAGS, **kwargs)
