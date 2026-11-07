"""Compile one Blink source with its real header closure and compiler options."""

load("@chromium//native:blink_core_sources.bzl", "LIBRARIES")
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

def blink_compile_probe(name):
    """Reuse compilation context without requesting the owning library's objects."""
    library = LIBRARIES["//third_party/blink/renderer/core:core"]
    _compilation_headers(
        name = name + "_headers",
        library = "@chromium//native:" + library["name"],
    )
    cc_library(
        name = name,
        srcs = ["@chromium//:third_party/blink/renderer/core/layout/layout_box.cc"],
        copts = library["copts"],
        local_defines = library["defines"],
        deps = [":" + name + "_headers"],
        features = ["cc_include_scanning"],
        # Skia selects these headers through macro includes.
        additional_compiler_inputs = [
            "@chromium//:skia/config/SkUserConfig.h",
            "@chromium//:skia/config/sk_ref_cnt_ext_release.h",
            "@chromium//:skia/ext/skia_histogram.h",
        ],
        tags = ["manual"],
    )
