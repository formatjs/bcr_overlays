"""Expose pinned executable files as Bazel tools."""

def _executable_impl(ctx):
    output = ctx.actions.declare_file(ctx.label.name + ".bin")
    ctx.actions.symlink(output = output, target_file = ctx.file.src, is_executable = True)
    return [DefaultInfo(executable = output, runfiles = ctx.runfiles(files = [ctx.file.src], transitive_files = ctx.attr.runtime[DefaultInfo].files if ctx.attr.runtime else depset()))]

import_executable = rule(
    implementation = _executable_impl,
    executable = True,
    attrs = {"runtime": attr.label(cfg = "exec"), "src": attr.label(allow_single_file = True, mandatory = True, cfg = "exec")},
)
