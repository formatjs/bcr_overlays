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

def _blink_library_probe(name, library, repository, sources):
    _compilation_headers(
        name = name + "_headers",
        library = repository + "//native:" + library["name"],
    )
    cc_library(
        name = name,
        srcs = [repository + "//:" + source for source in sources],
        copts = library["copts"],
        local_defines = library["defines"],
        linkstatic = True,
        deps = [":" + name + "_headers"],
        features = ["cc_include_scanning"],
        # Skia selects these headers through macro includes.
        additional_compiler_inputs = [
            repository + "//:base/component_export.h",
            repository + "//:skia/config/SkUserConfig.h",
            repository + "//:skia/config/sk_ref_cnt_ext_debug.h",
            repository + "//:skia/config/sk_ref_cnt_ext_release.h",
            repository + "//:skia/ext/skia_histogram.h",
            # Preserve the directory used by ../../skia/config includes.
            repository + "//native:blink_core_forwarders/third_party/re2/src/re2/re2.h",
        ],
        tags = ["manual"],
    )

def blink_compile_probe(name, libraries, repository = "@chromium"):
    """Reuse each source's real context without requesting its owner's objects."""
    _blink_library_probe(name, libraries["//third_party/blink/renderer/core:core"], repository, [
        "third_party/blink/renderer/core/layout/layout_box.cc",
        "third_party/blink/renderer/core/layout/layout_view.cc",
        "third_party/blink/renderer/core/paint/svg_object_painter.cc",
        "third_party/blink/renderer/core/css/css_palette_mix_value.cc",
        "third_party/blink/renderer/core/css/css_relative_color_value.cc",
    ])
    _blink_library_probe(name + "_canvas", libraries["//third_party/blink/renderer/core/probe:probe"], repository, [
        "third_party/blink/renderer/core/probe/core_probes.cc",
    ])
