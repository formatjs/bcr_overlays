"""Expose Chromium's complete prepatched Node source tree to native actions."""

load(":python_action.bzl", "ChromiumFilesInfo", "chromium_filegroup")

def _package_inputs_impl(ctx):
    suffix = "typescript/package.json"
    if not ctx.file.manifest.path.endswith(suffix):
        fail("invalid Node source archive anchor")
    root = ctx.file.manifest.path[:-len(suffix)]
    mappings = []
    for file in ctx.attr.src[DefaultInfo].files.to_list():
        if not file.path.startswith(root):
            fail("npm file outside package root: %s" % file.path)
        mappings.append((file, ctx.attr.logical_root + "/" + file.path[len(root):]))
    return [
        DefaultInfo(files = depset([file for file, _ in mappings])),
        ChromiumFilesInfo(mappings = depset(mappings)),
    ]

_package_inputs = rule(
    implementation = _package_inputs_impl,
    attrs = {
        "src": attr.label(mandatory = True),
        "manifest": attr.label(allow_single_file = True, mandatory = True),
        "logical_root": attr.string(mandatory = True),
    },
)

def chromium_npm_inputs(name, src = "@chromium_node_modules//:files", manifest = "@chromium_node_modules//:node_modules/typescript/package.json", logical_root = "third_party/node/node_modules"):
    """Declare locked npm runtime sources at their installed dependency paths.

    Args:
        name: Target collecting the complete WebUI toolchain source tree.
        src: Locked npm source archive.
        manifest: TypeScript package anchor within the archive.
        logical_root: Original checkout path for installed packages.
    """
    _package_inputs(
        name = name + "_archive",
        src = src,
        manifest = manifest,
        logical_root = logical_root,
    )
    chromium_filegroup(
        name = name,
        deps = [":" + name + "_archive"],
    )
