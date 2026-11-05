"""Expose patched, cached V8 sources at Chromium paths."""

def _impl(ctx):
    root = ctx.path(ctx.attr.catalog).dirname
    source = ctx.path(ctx.attr.archive).dirname.dirname
    for path in source.readdir():
        if path.basename not in ["BUILD", "BUILD.bazel", "__source__"]:
            ctx.symlink(path, "v8/" + path.basename)
    ctx.symlink(root.get_child("build/v8.BUILD.bazel"), "BUILD.bazel")

chromium_v8_repository = repository_rule(
    implementation = _impl,
    attrs = {
        "archive": attr.label(mandatory = True),
        "catalog": attr.label(mandatory = True),
    },
)
