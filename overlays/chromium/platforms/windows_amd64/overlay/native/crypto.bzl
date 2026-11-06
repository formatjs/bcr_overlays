"""Captured Windows crypto and CBOR implementations."""

load(":crypto_sources.bzl", "COPTS", "DEFINES", "HEADERS", "LIBS", "SOURCES")
load(":host_support.bzl", cc_library = "platform_cc_library")

def native_crypto():
    for name, dependencies in {
        "cbor": [":base"],
        "crypto": [":base", ":cbor", "//third_party/boringssl"],
    }.items():
        cc_library(
            name = name,
            srcs = ["//:" + path for path in SOURCES[name]],
            hdrs = ["//:" + path for path in HEADERS[name]] + [":all_buildflags", "//build:precompile.h"],
            includes = ["..", "gen"],
            copts = COPTS[name],
            local_defines = DEFINES[name],
            linkopts = ["-DEFAULTLIB:" + library for library in LIBS[name]],
            linkstatic = True,
            deps = dependencies,
        )
