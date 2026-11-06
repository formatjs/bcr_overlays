"""Captured macOS crypto and CBOR implementations."""

load(":crypto_sources.bzl", "COPTS", "DEFINES", "FRAMEWORKS", "HEADERS", "OBJCXX_COPTS", "OBJCXX_SOURCES", "SOURCES")
load(":host_support.bzl", cc_library = "platform_cc_library")
load(":objcxx.bzl", "objcxx_library")

def native_crypto():
    for name, dependencies in {
        "cbor": [":base"],
        "crypto": [":base", ":cbor", "//third_party/boringssl"],
    }.items():
        cc_library(
            name = name + "_headers",
            hdrs = ["//:" + path for path in HEADERS[name]] + [":all_buildflags"],
            includes = ["..", "gen"],
            deps = dependencies,
        )
        if OBJCXX_SOURCES[name]:
            objcxx_library(
                name = name + "_objcxx",
                srcs = ["//:" + path for path in OBJCXX_SOURCES[name]],
                copts = OBJCXX_COPTS[name],
                local_defines = DEFINES[name],
                deps = [":" + name + "_headers"],
                alwayslink = True,
                target_compatible_with = ["@platforms//os:macos"],
            )
        cc_library(
            name = name,
            srcs = ["//:" + path for path in SOURCES[name]],
            copts = COPTS[name],
            local_defines = DEFINES[name],
            linkstatic = True,
            linkopts = [option for framework in FRAMEWORKS[name] for option in ["-framework", framework]],
            deps = [":" + name + "_headers", ":" + name + "_objcxx"] if OBJCXX_SOURCES[name] else [":" + name + "_headers"],
        )
