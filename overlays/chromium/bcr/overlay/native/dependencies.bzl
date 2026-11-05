"""Pinned Chromium DEPS sources used by native build rules."""

def _quiche_source_impl(ctx):
    prefix = "net/third_party/quiche/src"
    ctx.download_and_extract(
        url = "https://github.com/google/quiche/archive/c0df0d316bd7e4ddf44e5ba094b5c5b061d94b0c.tar.gz",
        sha256 = "23e9c360d3a42e8d9cd006e0fcafebe9387e9f72bd722d5a0d0ba92ca349b110",
        stripPrefix = "quiche-c0df0d316bd7e4ddf44e5ba094b5c5b061d94b0c",
        output = prefix,
    )

    # Project original Chromium paths without upstream Bazel package boundaries.
    for path in ["BUILD.bazel", "build/BUILD.bazel", "quiche/BUILD.bazel"]:
        ctx.delete(prefix + "/" + path)
    ctx.symlink(ctx.attr.build_file, "BUILD.bazel")

_quiche_source = repository_rule(
    implementation = _quiche_source_impl,
    attrs = {"build_file": attr.label(mandatory = True)},
)

def _dependencies_impl(ctx):
    _quiche_source(
        name = "chromium_quiche",
        build_file = Label(":quiche_repository.BUILD.bazel"),
    )
    return ctx.extension_metadata(reproducible = True)

chromium_dependencies = module_extension(implementation = _dependencies_impl)
