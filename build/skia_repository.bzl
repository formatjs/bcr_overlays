"""Project cached Skia sources at Chromium paths without upstream packages."""

def _impl(ctx):
    root = ctx.path(ctx.attr.catalog).dirname
    packages = json.decode(ctx.read(root.get_child("build/skia_packages.json")))
    split = {"": True}
    for package in packages:
        parts = package.split("/")[:-1]
        for count in range(1, len(parts) + 1):
            split["/".join(parts[:count])] = True
    source = ctx.path(ctx.attr.archive).dirname.dirname
    pending = [(source, "")]
    for _ in range(32):
        next_level = []
        for directory, prefix in pending:
            for path in sorted(directory.readdir(), key = str):
                relative = prefix + path.basename
                if path.basename in ["BUILD", "BUILD.bazel"]:
                    continue
                if path.is_dir and relative in split:
                    next_level.append((path, relative + "/"))
                else:
                    ctx.symlink(path, "third_party/skia/" + relative)
        pending = next_level
        if not pending:
            break
    if pending:
        fail("Skia source tree exceeds supported depth")
    ctx.symlink(root.get_child("build/skia.BUILD.bazel"), "BUILD.bazel")

chromium_skia_repository = repository_rule(
    implementation = _impl,
    attrs = {
        "archive": attr.label(mandatory = True),
        "catalog": attr.label(mandatory = True),
    },
)
