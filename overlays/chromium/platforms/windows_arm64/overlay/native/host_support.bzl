"""Keep Linux host tool dependencies on the native source configuration."""

load("@rules_cc//cc:cc_library.bzl", _cc_library = "cc_library")

def platform_cc_library(name, **kwargs):
    _cc_library(name = name + "_windows", **kwargs)
    native.alias(name = name, actual = select({
        "@platforms//os:windows": ":" + name + "_windows",
        "//conditions:default": "@chromium//" + native.package_name() + ":" + name,
    }))
