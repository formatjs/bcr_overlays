"""Use the original AMD64 support libraries for host generators."""

load("@rules_cc//cc:cc_library.bzl", _cc_library = "cc_library")

def platform_cc_library(name, **kwargs):
    _cc_library(name = name + "_arm64", **kwargs)
    native.alias(
        name = name,
        actual = select({
            "@platforms//cpu:aarch64": ":" + name + "_arm64",
            "//conditions:default": "@chromium//" + native.package_name() + ":" + name,
        }),
    )
