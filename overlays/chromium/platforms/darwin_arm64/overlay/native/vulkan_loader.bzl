"""Captured macOS Vulkan loader, linked statically into ANGLE."""

load(":host_support.bzl", cc_library = "platform_cc_library")
load(":vulkan_loader_sources.bzl", "LIBRARIES", "SHARED_HEADERS")

def native_vulkan_loader():
    library = LIBRARIES["//third_party/vulkan-loader/src:libvulkan"]
    cc_library(
        name = library["name"],
        srcs = library["srcs"],
        hdrs = sorted({path: True for path in SHARED_HEADERS + library["hdrs"]}),
        copts = library["c_copts"],
        local_defines = library["defines"],
        includes = library["includes"],
        linkopts = library["linkopts"],
        deps = sorted({path: True for path in library["deps"] + [
            "@chromium_vulkan_loader//:headers",
            "@vulkan_headers//:vulkan_headers",
        ]}),
    )
    native.alias(name = "vulkan_loader", actual = ":" + library["name"])
