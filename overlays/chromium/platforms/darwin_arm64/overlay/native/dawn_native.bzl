"""Captured Dawn native library; runtime shared libraries remain separate."""

load("@bazel_skylib//rules:write_file.bzl", "write_file")
load(":dawn_native_sources.bzl", "ACTIONS", "LIBRARIES", "METADATA", "PUBLIC_DEFINES", "RUNTIME_DEPS", "SHARED_HEADERS")
load(":generated_files.bzl", "CAPTURED_FILES")
load(":host_support.bzl", cc_library = "platform_cc_library")
load(":objcxx.bzl", "objcxx_library")
load(":python_action.bzl", "chromium_python_action")

def native_dawn_backend():
    write_file(
        name = "dawn_native_runtime_requirements",
        out = "dawn_native_runtime_requirements.json",
        content = [json.encode_indent(RUNTIME_DEPS, indent = "  ")],
    )
    for path, content in METADATA.items():
        if path in CAPTURED_FILES:
            continue
        if path == "gpu/webgpu/DAWN_VERSION":
            continue
        write_file(
            name = "dawn_native_metadata_" + path.replace("/", "_"),
            out = path if path.startswith("gen/") else "metadata/" + path,
            content = [content],
        )
    for action in ACTIONS:
        chromium_python_action(**action)
    cc_library(
        name = "dawn_native_headers",
        hdrs = SHARED_HEADERS + [":all_buildflags"],
        includes = ["..", "gen", "gen/third_party/dawn/include", "gen/third_party/dawn/src"],
        defines = PUBLIC_DEFINES,
        deps = [
            ":dawn_cpp_headers",
            ":tint_headers",
            "@chromium_dawn//:source_headers",
            "@chromium_dawn//:khronos_headers",
            "@vulkan_utility_libraries//:vulkan_utility_headers",
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
            deps = [":dawn_native_headers"] + library["deps"],
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
        if c_sources:
            cc_library(
                name = library["name"] + "_c",
                srcs = c_sources,
                copts = library["c_copts"],
                **common
            )
            common["deps"] = common["deps"] + [":" + library["name"] + "_c"]
        cc_library(
            name = library["name"],
            srcs = [source for source in library["srcs"] if source not in c_sources],
            copts = library["copts"],
            **common
        )
    native.alias(
        name = "dawn_native_library",
        actual = ":" + LIBRARIES["//third_party/dawn/src/dawn/native:static"]["name"],
    )
