"""Pinned DIA SDK matching the Microsoft toolset used by hermetic LLVM."""

def _dia_impl(ctx):
    if ctx.os.environ.get("BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA") != "1":
        fail("DIA SDK requires --repo_env=BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA=1")
    ctx.download_and_extract(
        url = "https://download.visualstudio.microsoft.com/download/pr/86c5eaf6-8fd6-43ce-b7d1-89137b2c3ec7/795964264cae1180146529a7520b50d920f070ce3d6d77c295a73a90d857b21d/Microsoft.VisualCpp.DIA.SDK.vsix",
        sha256 = "795964264cae1180146529a7520b50d920f070ce3d6d77c295a73a90d857b21d",
        type = "zip",
    )
    ctx.file("BUILD.bazel", "\n".join([
        'load("@rules_cc//cc:cc_import.bzl", "cc_import")',
        'load("@rules_cc//cc:cc_library.bzl", "cc_library")',
        'package(default_visibility = ["//visibility:public"])',
        "cc_import(",
        '    name = "guids",',
        "    static_library = select({",
        '        "@platforms//cpu:aarch64": "Contents/DIA%20SDK/lib/arm64/diaguids.lib",',
        '        "@platforms//cpu:x86_64": "Contents/DIA%20SDK/lib/amd64/diaguids.lib",',
        "    }),",
        '    target_compatible_with = ["@platforms//os:windows"],',
        ")",
        "cc_library(",
        '    name = "sdk",',
        '    hdrs = glob(["Contents/DIA%20SDK/include/**"]),',
        '    includes = ["Contents/DIA%20SDK/include"],',
        '    deps = [":guids"],',
        '    target_compatible_with = ["@platforms//os:windows"],',
        ")",
        "",
    ]))

chromium_msvc_dia = repository_rule(
    implementation = _dia_impl,
    environ = ["BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA"],
)
