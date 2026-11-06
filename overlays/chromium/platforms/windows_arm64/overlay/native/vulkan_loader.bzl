"""Captured Windows Vulkan loader DLL and its MSVC import library."""

load("@rules_cc//cc:cc_binary.bzl", "cc_binary")
load("@rules_cc//cc:cc_import.bzl", "cc_import")
load(":host_support.bzl", cc_library = "platform_cc_library")
load(":python_action.bzl", "chromium_python_action")
load(":vulkan_loader_sources.bzl", "ACTIONS", "LIBRARIES", "SHARED_HEADERS")
load(":windows_resources.bzl", "chromium_windows_resource")

def native_vulkan_loader():
    for action in ACTIONS:
        chromium_python_action(**action)
    library = LIBRARIES["//third_party/vulkan-loader/src:libvulkan"]
    cc_library(
        name = "vulkan_loader_headers",
        hdrs = sorted({path: True for path in SHARED_HEADERS + library["hdrs"]}),
        includes = library["includes"],
        deps = sorted({path: True for path in library["deps"] + [
            "@chromium_vulkan_loader//:headers",
            "@vulkan_headers//:vulkan_headers",
        ]}),
    )
    resources = []
    for index, source in enumerate(library.get("resource_srcs", [])):
        name = library["name"] + "_resource_" + str(index)
        chromium_windows_resource(
            name = name,
            src = source,
            defines = library["resource_defines"],
            includes = library["includes"],
            deps = [":vulkan_loader_headers"],
        )
        resources.append(":" + name)
    cc_binary(
        name = "vulkan-1.dll",
        srcs = library["srcs"] + library["hdrs"] + resources,
        includes = library["includes"],
        copts = library["c_copts"],
        local_defines = library["defines"],
        linkopts = library["linkopts"],
        linkshared = True,
        linkstatic = True,
        win_def_file = library["win_def_file"],
        deps = [":vulkan_loader_headers"],
    )
    native.filegroup(name = "vulkan_import_library", srcs = [":vulkan-1.dll"], output_group = "interface_library")
    cc_import(name = library["name"], shared_library = ":vulkan-1.dll", interface_library = ":vulkan_import_library")
    native.alias(name = "vulkan_loader", actual = ":" + library["name"])
