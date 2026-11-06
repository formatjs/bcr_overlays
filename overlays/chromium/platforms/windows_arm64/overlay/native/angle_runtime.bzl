"""Captured Windows MSVC ANGLE EGL/GLES libraries."""

load("@bazel_skylib//rules:write_file.bzl", "write_file")
load("@rules_cc//cc:cc_binary.bzl", "cc_binary")
load("@rules_cc//cc:cc_import.bzl", "cc_import")
load(":angle_runtime_sources.bzl", "ACTIONS", "LIBRARIES", "RUNTIME_DEPS", "SHARED_HEADERS", "TOOLS")
load(":host_support.bzl", cc_library = "platform_cc_library")
load(":objcxx.bzl", "objcxx_library")
load(":python_action.bzl", "chromium_python_action")
load(":tool_inputs.bzl", "chromium_tool_inputs")
load(":windows_resources.bzl", "chromium_windows_resource")

def native_angle_runtime():
    for name, tool in TOOLS.items():
        chromium_tool_inputs(name = name, **tool)
    for action in ACTIONS:
        chromium_python_action(**action)
    write_file(
        name = "angle_runtime_requirements",
        out = "angle_runtime_requirements.json",
        content = [json.encode_indent(RUNTIME_DEPS, indent = "  ")],
    )
    cc_library(
        name = "angle_runtime_headers",
        hdrs = SHARED_HEADERS,
        includes = ["../third_party/zlib/google"],
        deps = [
            "@chromium_angle//:headers",
            "@chromium_vma//:headers",
            "@spirv_headers//:spirv_cpp_headers",
            ":spirv_headers",
        ],
    )
    for original, library in LIBRARIES.items():
        c_sources = [source for source in library["srcs"] if source.endswith(".c")]
        common = dict(
            hdrs = library["hdrs"],
            includes = library["includes"],
            local_defines = library["defines"],
            linkopts = library["linkopts"],
            linkstatic = True,
            deps = [":angle_runtime_headers"] + library["deps"],
        )
        resources = []
        for index, source in enumerate(library.get("resource_srcs", [])):
            target = library["name"] + "_resource_" + str(index)
            chromium_windows_resource(
                name = target,
                src = source,
                defines = library["resource_defines"],
                includes = library["includes"],
                deps = common["deps"],
            )
            resources.append(":" + target)
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
        sources = [source for source in library["srcs"] if source not in c_sources] + resources
        if library["kind"] == "shared_library":
            filename = original.split(":")[-1] + ".dll"
            headers = common.pop("hdrs")
            cc_binary(
                name = filename,
                srcs = sources + headers,
                copts = library["copts"],
                linkshared = True,
                win_def_file = library.get("win_def_file"),
                **common
            )
            native.filegroup(
                name = filename + "_import_library",
                srcs = [":" + filename],
                output_group = "interface_library",
            )
            cc_import(
                name = library["name"],
                shared_library = ":" + filename,
                interface_library = ":" + filename + "_import_library",
            )
        else:
            cc_library(
                name = library["name"],
                srcs = sources,
                copts = library["copts"],
                alwayslink = library["kind"] == "source_set",
                **common
            )
    native.filegroup(name = "angle_runtime", srcs = [":libEGL.dll", ":libGLESv2.dll"])
