"""Original Linux crypto, NSS utilities and CBOR."""

load("@rules_cc//cc:cc_library.bzl", "cc_library")
load(":crypto_sources.bzl", "COPTS", "DEFINES", "HEADERS", "SOURCES")

def native_crypto():
    for name, deps in {
        "cbor": [":base"],
        "crypto": [":base", ":cbor", "//third_party/boringssl", "@nss"],
    }.items():
        cc_library(
            name = name,
            srcs = ["//:" + path for path in SOURCES[name]],
            hdrs = ["//:" + path for path in HEADERS[name]] + [":all_buildflags"],
            includes = ["..", "gen"],
            copts = COPTS[name],
            local_defines = DEFINES[name],
            linkstatic = True,
            deps = deps,
        )
