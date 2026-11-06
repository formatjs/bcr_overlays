"""Pinned ATL headers matching hermetic LLVM's Microsoft toolset."""

def _atl_impl(ctx):
    if ctx.os.environ.get("BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA") != "1":
        fail("ATL requires --repo_env=BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA=1")
    ctx.download_and_extract(
        url = "https://download.visualstudio.microsoft.com/download/pr/eef0996f-4334-4b1a-a344-4d13e27ac052/64e638a9e62e056a14b16cf66c2d7710291a6d408953065e2a8caf45ab995e42/Microsoft.VC.14.50.18.0.ATL.Headers.base.vsix",
        sha256 = "64e638a9e62e056a14b16cf66c2d7710291a6d408953065e2a8caf45ab995e42",
        type = "zip",
    )
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
