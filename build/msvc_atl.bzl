"""Pinned ATL headers matching hermetic LLVM's Microsoft toolset."""

def _atl_impl(ctx):
    if ctx.os.environ.get("BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA") != "1":
        fail("ATL requires --repo_env=BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA=1")
    ctx.download_and_extract(
        url = "https://download.visualstudio.microsoft.com/download/pr/eef0996f-4334-4b1a-a344-4d13e27ac052/64e638a9e62e056a14b16cf66c2d7710291a6d408953065e2a8caf45ab995e42/Microsoft.VC.14.50.18.0.ATL.Headers.base.vsix",
        sha256 = "64e638a9e62e056a14b16cf66c2d7710291a6d408953065e2a8caf45ab995e42",
        type = "zip",
    )
    header = "Contents/VC/Tools/MSVC/14.50.35717/atlmfc/include/cstringt.h"
    text = ctx.read(header)
    include = "#include <yvals_core.h>"
    if text.count(include) != 1:
        fail("ATL CString STL compatibility patch no longer matches")
    ctx.file(header, text.replace(include, "#ifdef _LIBCPP_VERSION\n#include <version>\n#else\n" + include + "\n#endif"), executable = False)
    header = "Contents/VC/Tools/MSVC/14.50.35717/atlmfc/include/atlsecurity.h"
    text = ctx.read(header)
    if text.count("throw;") != 3:
        fail("ATL security exception patch no longer matches")
    ctx.file(header, text.replace("throw;", "_ATLRETHROW;"), executable = False)
    ctx.file("BUILD.bazel", "\n".join([
        'load("@rules_cc//cc:cc_library.bzl", "cc_library")',
        "cc_library(",
        '    name = "headers",',
        '    hdrs = glob(["Contents/VC/Tools/MSVC/14.50.35717/atlmfc/include/**"]),',
        '    includes = ["Contents/VC/Tools/MSVC/14.50.35717/atlmfc/include"],',
        '    target_compatible_with = ["@platforms//os:windows"],',
        '    visibility = ["//visibility:public"],',
        ")",
        "",
    ]))

chromium_msvc_atl = repository_rule(
    implementation = _atl_impl,
    environ = ["BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA"],
)

def _atl_libraries_impl(ctx):
    if ctx.os.environ.get("BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA") != "1":
        fail("ATL requires --repo_env=BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA=1")
    for architecture, package, digest in [
        ("arm64", "ARM64", "22be0cf76c200576446f3ec0e2043d3b46b36a5be397d706ea1665154b0864de"),
        ("x64", "X64", "6625a6d9749797d140f64460dc9a846dc702d133e790b2eb636485f0fa8021db"),
    ]:
        ctx.download_and_extract(
            url = "https://download.visualstudio.microsoft.com/download/pr/eef0996f-4334-4b1a-a344-4d13e27ac052/" + digest + "/Microsoft.VC.14.50.18.0.ATL." + package + ".base.vsix",
            sha256 = digest,
            type = "zip",
            output = architecture,
        )
    ctx.file("BUILD.bazel", "\n".join([
        'load("@rules_cc//cc:cc_import.bzl", "cc_import")',
        "cc_import(",
        '    name = "atls",',
        "    static_library = select({",
        '        "@platforms//cpu:aarch64": "arm64/Contents/VC/Tools/MSVC/14.50.35717/atlmfc/lib/arm64/atls.lib",',
        '        "@platforms//cpu:x86_64": "x64/Contents/VC/Tools/MSVC/14.50.35717/atlmfc/lib/x64/atls.lib",',
        "    }),",
        '    target_compatible_with = ["@platforms//os:windows"],',
        '    visibility = ["//visibility:public"],',
        ")",
        "",
    ]))

chromium_msvc_atl_libraries = repository_rule(
    implementation = _atl_libraries_impl,
    environ = ["BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA"],
)
