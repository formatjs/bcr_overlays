"""Complete captured Chromium Skia graph with its original configuration."""

load(":cxx_bridge.bzl", "chromium_cxx_bridge")
load(":host_support.bzl", cc_library = "platform_cc_library")
load(":objcxx.bzl", "objcxx_library")
load(":python_action.bzl", "chromium_python_action")
load(":skia_sources.bzl", "ACTIONS", "BRIDGES", "LIBRARIES", "PUBLIC_DEFINES", "SHARED_HEADERS")

def native_skia():
    for bridge in BRIDGES:
        chromium_cxx_bridge(**bridge)
    for action in ACTIONS:
        chromium_python_action(**action)
    cc_library(
        name = "skia_headers",
        hdrs = SHARED_HEADERS + [":all_buildflags"],
        includes = ["..", "gen", "gen/third_party/skia"],
        defines = PUBLIC_DEFINES,
        deps = [
            ":base_headers",
            ":dawn_cpp_headers",
            "@chromium_skia//:headers",
            "@vulkan_headers//:vulkan_headers",
        ],
    )
    for original, library in LIBRARIES.items():
        dependencies = [":skia_headers"] + library["deps"]
        if library.get("objcxx_srcs"):
            cc_library(
                name = library["name"] + "_headers",
                hdrs = library["hdrs"],
                includes = library["includes"],
                deps = dependencies,
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
            dependencies.append(":" + library["name"] + "_objcxx")
        cc_library(
            name = library["name"],
            srcs = library["srcs"],
            hdrs = library["hdrs"],
            includes = library["includes"],
            copts = library["copts"],
            local_defines = library["defines"],
            linkopts = library["linkopts"],
            linkstatic = True,
            deps = dependencies,
        )
    native.alias(name = "skia", actual = ":" + LIBRARIES["//skia:skia"]["name"])
