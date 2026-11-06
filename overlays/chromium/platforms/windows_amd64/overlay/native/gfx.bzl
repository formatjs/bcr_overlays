"""Captured Windows ui/gfx sources and native providers."""

load(":browser_v8_sources.bzl", V8_LIBRARIES = "LIBRARIES")
load(":gfx_sources.bzl", "ACTIONS", "LIBRARIES", "SHARED_HEADERS")
load(":host_support.bzl", cc_library = "platform_cc_library")
load(":objcxx.bzl", "objcxx_library")
load(":python_action.bzl", "chromium_python_action")

def native_gfx():
    for action in ACTIONS:
        chromium_python_action(**action)
    cc_library(
        name = "gfx_headers",
        hdrs = SHARED_HEADERS + [":all_buildflags"],
        includes = ["..", "gen"],
        deps = ["@chromium_angle//:headers"],
    )
    for original, library in LIBRARIES.items():
        c_sources = [p for p in library["srcs"] if p.endswith(".c")]
        common = dict(
            hdrs = library["hdrs"],
            includes = library["includes"],
            local_defines = library["defines"],
            linkopts = library["linkopts"],
            linkstatic = True,
            deps = [":gfx_headers"] + library["deps"],
        )
        if library.get("objcxx_srcs"):
            cc_library(
                name = library["name"] + "_headers",
                hdrs = library["hdrs"],
                includes = library["includes"],
                deps = common["deps"],
            )
            objcxx_library(
                name = library["name"] + "_objcxx",
                srcs = library["objcxx_srcs"],
                copts = library["objcxx_copts"],
                local_defines = library["defines"],
                deps = [":" + library["name"] + "_headers"],
                alwayslink = True,
                target_compatible_with = ["@platforms//os:macos"],
            )
            common["deps"] = common["deps"] + [":" + library["name"] + "_objcxx"]
        if c_sources:
            cc_library(
                name = library["name"] + "_c",
                srcs = c_sources,
                copts = library["c_copts"],
                **common
            )
            common["deps"] = common["deps"] + [":" + library["name"] + "_c"]
        cc_library(
            name = library["name"],
            srcs = [p for p in library["srcs"] if p not in c_sources],
            copts = library["copts"],
            **common
        )
    for name, original in {
        "gfx": "//ui/gfx:gfx",
        "gfx_codec": "//ui/gfx/codec:codec",
        "gfx_memory_buffer": "//ui/gfx:memory_buffer_sources",
        "ui_data_pack": "//ui/base:ui_data_pack",
        "libdrm": "//third_party/libdrm:libdrm",
        "libsync": "//third_party/libsync:libsync",
        "zlib_compression_utils": "//third_party/zlib/google:compression_utils",
        "zlib_compression_utils_portable": "//third_party/zlib/google:compression_utils_portable",
    }.items():
        if original in LIBRARIES:
            native.alias(name = name, actual = ":" + LIBRARIES[original]["name"])
        elif original in V8_LIBRARIES:
            native.alias(name = name, actual = ":" + V8_LIBRARIES[original]["name"])
