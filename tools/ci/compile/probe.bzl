"""Compile representative Blink sources with their real compiler inputs."""

load("@rules_cc//cc:cc_library.bzl", "cc_library")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")
load(":batch_sources.bzl", BATCH_SOURCES = "SOURCES")

def _headers_impl(ctx):
    return [
        DefaultInfo(files = depset()),
        CcInfo(compilation_context = ctx.attr.library[CcInfo].compilation_context),
    ]

_compilation_headers = rule(
    implementation = _headers_impl,
    attrs = {"library": attr.label(mandatory = True, providers = [CcInfo])},
)

def _blink_library_probe(name, library, repository, sources, forwarders = "blink_core_forwarders"):
    _compilation_headers(
        name = name + "_headers",
        library = repository + "//native:" + library["name"],
    )
    cc_library(
        name = name,
        srcs = [repository + ("//native" if source.startswith(":") else "//:") + source for source in sources],
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
            repository + "//native:" + forwarders + "/third_party/re2/src/re2/re2.h",
        ],
        tags = ["manual"],
    )

def blink_compile_probe(name, libraries, repository = "@chromium", batch = False):
    """Reuse each source's real context without requesting its owner's objects."""
    sources = BATCH_SOURCES if batch else [
        "third_party/blink/renderer/core/layout/layout_box.cc",
        "third_party/blink/renderer/core/layout/layout_view.cc",
        "third_party/blink/renderer/core/paint/svg_object_painter.cc",
        "third_party/blink/renderer/core/css/css_palette_mix_value.cc",
        "third_party/blink/renderer/core/css/css_relative_color_value.cc",
    ]
    _blink_library_probe(name, libraries["//third_party/blink/renderer/core:core"], repository, sources)
    _blink_library_probe(name + "_canvas", libraries["//third_party/blink/renderer/core/probe:probe"], repository, [
        "third_party/blink/renderer/core/probe/core_probes.cc",
    ])

def host_blink_compile_probe(name, libraries, repository, wide = False):
    """Compile Linux ARM64's captured x64 host Blink context independently."""
    toolchain = "(//build/toolchain/linux:clang_x64_v8_arm64)"
    owners = [
        ("", "//third_party/blink/renderer/core:core", [
            "third_party/blink/renderer/core/layout/layout_box.cc",
            "third_party/blink/renderer/core/layout/layout_view.cc",
            "third_party/blink/renderer/core/paint/svg_object_painter.cc",
            "third_party/blink/renderer/core/css/css_palette_mix_value.cc",
            "third_party/blink/renderer/core/css/css_relative_color_value.cc",
        ] + ([":clang_x64_v8_arm64/gen/third_party/blink/renderer/core/html/html_permission_element_strings_map.cc"] if wide else [])),
        ("_canvas", "//third_party/blink/renderer/core/probe:probe", [
            "third_party/blink/renderer/core/probe/core_probes.cc",
        ]),
    ]
    if wide:
        owners += [
            ("_accessibility", "//third_party/blink/renderer/modules/accessibility:accessibility", [
                "third_party/blink/renderer/modules/accessibility/ax_object.cc",
                "third_party/blink/renderer/modules/accessibility/ax_node_object.cc",
            ]),
            ("_canvas2d", "//third_party/blink/renderer/modules/canvas:canvas", [
                "third_party/blink/renderer/modules/canvas/canvas2d/canvas_rendering_context_2d.cc",
            ]),
            ("_platform", "//third_party/blink/renderer/platform/wtf:wtf", [
                "third_party/blink/renderer/platform/wtf/date_math.cc",
            ]),
            ("_bindings", "//third_party/blink/renderer/bindings/modules/v8:v8", [
                ":clang_x64_v8_arm64/gen/third_party/blink/renderer/bindings/modules/v8/v8_video_frame.cc",
                ":clang_x64_v8_arm64/gen/third_party/blink/renderer/bindings/modules/v8/v8_webgl2_rendering_context_webgpu.cc",
            ]),
        ]
    for suffix, owner, sources in owners:
        library = dict(libraries[owner + toolchain])
        library["copts"] = library["copts"] + ["-I" + Label(root).workspace_root for root in library.get("include_roots", [])]
        _blink_library_probe(name + suffix, library, repository, sources, forwarders = "browser_forwarders")
