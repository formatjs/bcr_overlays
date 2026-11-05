"""Exact Debian runtime code matching Chromium's pinned SDK interfaces."""

def _platform_runtime_impl(ctx):
    manifest = json.decode(ctx.read(ctx.attr.manifest))
    if not manifest.get("packages"):
        fail("Runtime manifest lacks verified package hashes; run import_platform_runtime.py --download-dir first")
    for package in manifest["packages"]:
        filename = package["url"].split("/")[-1]
        name = filename.split("_")[0]
        archive = "packages/" + name
        ctx.download_and_extract(
            url = package.get("urls", [package["url"]]),
            sha256 = package["sha256"],
            type = "deb",
            output = archive,
        )
        payloads = [
            ctx.path(archive + "/" + filename)
            for filename in ["data.tar.xz", "data.tar.gz", "data.tar.zst", "data.tar.bz2"]
            if ctx.path(archive + "/" + filename).exists
        ]
        if len(payloads) != 1:
            fail("Expected one Debian data archive: " + name)
        ctx.extract(payloads[0], output = archive + "/root")
    libraries = manifest["libraries"]
    for soname, library in libraries.items():
        ctx.symlink("packages/" + library["package"] + "/root/" + library["interface"], soname)
    ctx.file("BUILD.bazel", "exports_files(" + repr(sorted(libraries)) + ")\nfilegroup(name = \"libraries\", srcs = " + repr(sorted(libraries)) + ", visibility = [\"//visibility:public\"])\n")

chromium_platform_runtime_repository = repository_rule(
    implementation = _platform_runtime_impl,
    attrs = {"manifest": attr.label(mandatory = True, allow_single_file = True)},
)

def _platform_headers_dispatch_impl(ctx):
    template = ctx.read(ctx.attr.template)
    names = [part.split('"')[0] for part in template.split('name = "')[1:]]
    names.append("usr/include/x86_64-linux-gnu/pci/config.h")
    lines = ['package(default_visibility = ["//visibility:public"])']
    for name in names:
        arm64 = name.replace("x86_64-linux-gnu", "aarch64-linux-gnu")
        lines.append("alias(name = " + repr(name) + ", actual = select({" +
                     repr("@platforms//cpu:aarch64") + ": " + repr("@chromium_platform_headers_arm64//:" + arm64) + ", " +
                     repr("//conditions:default") + ": " + repr("@chromium_platform_headers//:" + name) + "}))")
    ctx.file("BUILD.bazel", "\n".join(lines) + "\n")

chromium_platform_headers_dispatch = repository_rule(
    implementation = _platform_headers_dispatch_impl,
    attrs = {"template": attr.label(mandatory = True, allow_single_file = True)},
)
