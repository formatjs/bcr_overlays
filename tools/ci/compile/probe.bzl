"""Compile representative Blink sources with their real compiler inputs."""

load("@rules_cc//cc:cc_library.bzl", "cc_library")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

def _headers_impl(ctx):
    return [
        DefaultInfo(files = depset()),
        CcInfo(compilation_context = ctx.attr.library[CcInfo].compilation_context),
    ]

_compilation_headers = rule(
    implementation = _headers_impl,
    attrs = {"library": attr.label(mandatory = True, providers = [CcInfo])},
)

def blink_compile_probe(name, libraries, repository = "@chromium"):
    """Reuse compilation context without requesting the owning library's objects."""
    library = libraries["//third_party/blink/renderer/core:core"]
    _compilation_headers(
        name = name + "_headers",
        library = repository + "//native:" + library["name"],
    )
    cc_library(
        name = name,
        srcs = [
            repository + "//:third_party/blink/renderer/core/layout/layout_box.cc",
            repository + "//:third_party/blink/renderer/core/layout/layout_view.cc",
            repository + "//:third_party/blink/renderer/core/paint/svg_object_painter.cc",
        ],
        copts = library["copts"],
        local_defines = library["defines"],
        linkstatic = True,
        deps = [":" + name + "_headers"],
        features = ["cc_include_scanning"],
        # Skia selects these headers through macro includes.
        additional_compiler_inputs = [
            repository + "//:skia/config/SkUserConfig.h",
            repository + "//:skia/config/sk_ref_cnt_ext_debug.h",
            repository + "//:skia/config/sk_ref_cnt_ext_release.h",
            repository + "//:skia/ext/skia_histogram.h",
            # Preserve the directory used by ../../skia/config includes.
            repository + "//native:blink_core_forwarders/third_party/re2/src/re2/re2.h",
        ],
        tags = ["manual"],
    )
