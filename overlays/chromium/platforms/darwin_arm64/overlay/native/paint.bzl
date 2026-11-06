"""Complete captured compositor paint closure, using Chromium's native providers."""

load(":host_support.bzl", cc_library = "platform_cc_library")
load(":mig.bzl", "chromium_mig_inputs")
load(":objcxx.bzl", "objcxx_library")
load(":paint_sources.bzl", "ACTIONS", "LIBRARIES", "SHARED_HEADERS")
load(":python_action.bzl", "chromium_python_action")

def native_paint():
    chromium_mig_inputs(name = "mac_mig_inputs")
    for action in ACTIONS:
        chromium_python_action(**action)
    cc_library(
        name = "paint_headers",
        hdrs = SHARED_HEADERS + [":all_buildflags"],
        includes = ["..", "gen"],
    )
    for original, library in LIBRARIES.items():
        common = dict(
            hdrs = library["hdrs"],
            includes = library["includes"],
            local_defines = library["defines"],
            linkopts = library["linkopts"],
            linkstatic = True,
            deps = [":paint_headers"] + library["deps"],
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
        c_sources = [p for p in library["srcs"] if p.endswith(".c")]
        assembly = [p for p in library["srcs"] if p.endswith((".S", ".s"))]
        for suffix, sources, options in [
            ("_c", c_sources, library.get("c_copts", [])),
            ("_asm", assembly, library.get("asm_copts", [])),
        ]:
            if sources:
                cc_library(name = library["name"] + suffix, srcs = sources, copts = options, **common)
                common["deps"] = common["deps"] + [":" + library["name"] + suffix]
        cc_library(
            name = library["name"],
            srcs = [p for p in library["srcs"] if p not in c_sources and p not in assembly],
            copts = library["copts"],
            **common
        )
    for name, original in {
        "paint": "//cc/paint:paint",
        "cc_base": "//cc/base:base",
        "cc_debug": "//cc/debug:debug",
        "gfx_color_space": "//ui/gfx:color_space",
        "gfx_skia": "//ui/gfx:gfx_skia",
        "gfx_animation": "//ui/gfx/animation:animation",
        "crash_keys": "//components/crash/core/common:crash_key",
        "crashpad_client": "//third_party/crashpad/crashpad/client:client",
    }.items():
        native.alias(name = name, actual = ":" + LIBRARIES[original]["name"])
