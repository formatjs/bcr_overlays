"""One dependency setup for the combined Chromium workspace."""

load("@bazel_tools//tools/build_defs/repo:git.bzl", "new_git_repository")
load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")
load(":angle_repository.bzl", "chromium_angle_repository", "chromium_angle_support")
load(":blink_sources.bzl", "chromium_blink_sources")
load(":browser_sources.bzl", "chromium_browser_sources")
load(":codecs.bzl", "chromium_codec_sources")
load(":compositor_sources.bzl", "chromium_compositor_sources")
load(":ffmpeg_sources.bzl", "chromium_ffmpeg_sources")
load(":fonts.bzl", "chromium_font_sources")
load(":graphics_sources.bzl", "chromium_graphics_sources")
load(":khronos_sources.bzl", "chromium_khronos_sources")
load(":libyuv_sources.bzl", "chromium_libyuv_sources")
load(":media_sources.bzl", "chromium_media_sources")
load(":ml_sources.bzl", "chromium_ml_sources")
load(":platform_runtime.bzl", "chromium_platform_headers_dispatch", "chromium_platform_runtime_repository")
load(":protobuf_javascript_sources.bzl", "chromium_protobuf_javascript_sources")
load(":pthreadpool_sources.bzl", "chromium_pthreadpool_sources")
load(":repositories.bzl", "chromium_dawn_repository", "chromium_overlay_archive", "chromium_overlay_repository", "chromium_quiche_repository")
load(":skia_repository.bzl", "chromium_skia_repository")
load(":swiftshader_sources.bzl", "chromium_swiftshader_sources")
load(":v8_repository.bzl", "chromium_v8_repository")
load(":vulkan_sources.bzl", "chromium_vulkan_sources")
load(":vulkan_tools_sources.bzl", "chromium_vulkan_tools_sources")
load(":wayland_protocol_sources.bzl", "chromium_wayland_protocol_sources")

_OVERLAYS = [
    "angle",
    "chromium",
    "chromium_icu",
    "compact_enc_det",
    "dragonbox",
    "fp16",
    "ipcz",
    "linux-syscall-support",
    "nspr",
    "nss",
    "perfetto",
    "skia",
    "v8",
]

def _dependencies_impl(ctx):
    chromium_platform_runtime_repository(
        name = "chromium_platform_runtime",
        manifest = Label("//overlays/chromium:native/platform_runtime.json"),
    )
    chromium_platform_runtime_repository(
        name = "chromium_platform_runtime_arm64",
        manifest = Label("//overlays/chromium:platforms/linux_arm64/platform_runtime.json"),
    )
    chromium_platform_headers_dispatch(
        name = "chromium_platform_headers_cross",
        template = Label("//build:platform_headers.BUILD.bazel"),
    )
    chromium_ffmpeg_sources()
    chromium_media_sources(ctx)
    chromium_compositor_sources(ctx)
    chromium_blink_sources(ctx)
    chromium_browser_sources(ctx)
    chromium_ml_sources(ctx)
    chromium_pthreadpool_sources()
    chromium_libyuv_sources()
    chromium_wayland_protocol_sources()
    chromium_angle_support()
    chromium_protobuf_javascript_sources()
    chromium_font_sources()
    chromium_graphics_sources()
    chromium_khronos_sources()
    chromium_vulkan_sources()
    chromium_vulkan_tools_sources()
    chromium_swiftshader_sources()
    chromium_codec_sources()
    for name in _OVERLAYS:
        archive_name = name + "_sources"
        chromium_overlay_archive(name = archive_name, overlay = name, catalog = Label("//:overlays.json"))
        chromium_overlay_repository(
            name = name,
            overlay = name,
            archive = "@" + archive_name + "//__source__:anchor",
            catalog = Label("//:overlays.json"),
        )
    chromium_overlay_repository(
        name = "chromium_linux_arm64",
        overlay = "chromium",
        variant = "linux_arm64",
        archive = "@chromium_sources//__source__:anchor",
        catalog = Label("//:overlays.json"),
    )
    chromium_v8_repository(name = "chromium_v8", archive = "@v8_sources//__source__:anchor", catalog = Label("//:overlays.json"))
    chromium_angle_repository(name = "chromium_angle", archive = "@angle_sources//__source__:anchor", catalog = Label("//:overlays.json"))
    chromium_skia_repository(name = "chromium_skia", archive = "@skia_sources//__source__:anchor", catalog = Label("//:overlays.json"))
    chromium_dawn_repository(name = "chromium_dawn", catalog = Label("//:overlays.json"))
    chromium_quiche_repository(name = "chromium_quiche", catalog = Label("//:overlays.json"))
    new_git_repository(
        name = "chromium_sqlite",
        remote = "https://chromium.googlesource.com/chromium/deps/sqlite",
        commit = "7d348fc79216a09b864ff881d8561a6222301666",
        build_file = Label("//build:sqlite.BUILD.bazel"),
    )
    http_archive(
        name = "chromium_platform_headers",
        type = "tar.xz",
        urls = ["https://commondatastorage.googleapis.com/chrome-linux-sysroot/36a164623d03f525e3dfb783a5e9b8a00e98e1ddd2b5cff4e449bd016dd27e50"],
        sha256 = "36a164623d03f525e3dfb783a5e9b8a00e98e1ddd2b5cff4e449bd016dd27e50",
        build_file = Label("//build:platform_headers.BUILD.bazel"),
    )
    http_archive(
        name = "chromium_platform_headers_arm64",
        type = "tar.xz",
        urls = ["https://commondatastorage.googleapis.com/chrome-linux-sysroot/2f915d821eec27515c0c6d21b69898e23762908d8d7ccc1aa2a8f5f25e8b7e18"],
        sha256 = "2f915d821eec27515c0c6d21b69898e23762908d8d7ccc1aa2a8f5f25e8b7e18",
        build_file_content = ctx.read(Label("//build:platform_headers.BUILD.bazel")).replace("x86_64-linux-gnu", "aarch64-linux-gnu"),
    )
    return ctx.extension_metadata(
        reproducible = True,
        root_module_direct_deps = _OVERLAYS + ["chromium_linux_arm64", "chromium_platform_headers_arm64", "chromium_platform_headers_cross", "chromium_platform_runtime_arm64"] + ["chromium_platform_runtime", "chromium_catapult"] + ["chromium_openscreen", "chromium_pdfium", "chromium_readability"] + ["chromium_anonymous_tokens", "chromium_content_analysis_sdk", "chromium_dom_distiller_js", "chromium_ink", "chromium_ink_stroke_modeler", "chromium_libaddressinput", "chromium_xdg_utils"] + ["chromium_search_engines_data", "chromium_cld3", "chromium_emoji_segmenter", "chromium_ots", "chromium_material_color_utilities", "chromium_smhasher", "chromium_libphonenumber", "chromium_crabbyavif", "chromium_cros_system_api", "chromium_devtools_frontend", "chromium_devtools_esbuild", "chromium_xcomposite", "chromium_xtst", "chromium_webrtc", "chromium_libsrtp", "chromium_federated_compute", "chromium_cdm_api", "chromium_libgav1", "chromium_leveldatabase", "chromium_ffmpeg", "chromium_ruy", "chromium_eigen3", "chromium_gemmlowp", "chromium_farmhash", "chromium_neon_2_sse", "chromium_tflite", "chromium_xnnpack", "chromium_pthreadpool", "chromium_libyuv", "chromium_v8", "chromium_wayland_protocols", "chromium_kde_protocols", "chromium_protobuf_javascript", "chromium_vulkan_tools", "chromium_pciutils", "chromium_angle", "chromium_vma", "chromium_swiftshader", "chromium_vulkan_utility", "chromium_vulkan_validation", "chromium_vulkan_loader", "chromium_egl_registry", "chromium_opengl_registry", "chromium_libdrm", "chromium_libsync", "chromium_skia", "chromium_jpeg", "chromium_webp", "chromium_wuffs", "chromium_freetype", "chromium_harfbuzz", "chromium_fontconfig", "chromium_dawn", "chromium_quiche", "chromium_sqlite", "chromium_platform_headers"],
        root_module_direct_dev_deps = [],
    )

chromium_dependencies = module_extension(implementation = _dependencies_impl)
