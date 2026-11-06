"""Captured Dawn native library; runtime shared libraries remain separate."""

load("@bazel_skylib//rules:write_file.bzl", "write_file")
load("@rules_cc//cc:cc_binary.bzl", "cc_binary")
load("@rules_cc//cc:cc_library.bzl", host_cc_library = "cc_library")
load(":dawn_native_sources.bzl", "ACTIONS", "COPIES", "LIBRARIES", "METADATA", "PUBLIC_DEFINES", "RUNTIME_DEPS", "SHARED_HEADERS", "TOOLS")
load(":generated_files.bzl", "CAPTURED_FILES")
load(":host_support.bzl", "platform_cc_library")
load(":objcxx.bzl", "objcxx_library")
load(":python_action.bzl", "chromium_python_action")
load(":resource_copy.bzl", "chromium_resource_copy")
load(":tool_inputs.bzl", "chromium_tool_inputs")
load(":windows_resources.bzl", "chromium_windows_resource")

def native_dawn_backend():
    cc_library = platform_cc_library
    for name, tool in TOOLS.items():
        chromium_tool_inputs(name = name, **tool)
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
    for copy in COPIES:
        chromium_resource_copy(**copy)
    for action in ACTIONS:
        chromium_python_action(**action)
    cc_library(
        name = "dawn_native_headers",
        hdrs = SHARED_HEADERS + [":all_buildflags"],
        includes = ["..", "gen", "gen/third_party/dawn/include", "gen/third_party/dawn/src"],
        defines = PUBLIC_DEFINES,
        deps = [
            ":dawn_cpp_headers",
            "@chromium_dxc//:headers",
            "@chromium_msvc_atl//:headers",
            "@chromium_msvc_atl_libraries//:atls",
            "@chromium_msvc_dia//:sdk",
            "@chromium_dawn//:dxc_build_headers",
            ":tint_headers",
            "@chromium_dawn//:source_headers",
            "@chromium_dawn//:khronos_headers",
            "@vulkan_utility_libraries//:vulkan_utility_headers",
        ],
    )
    host_cc_library(
        name = "dawn_dxc_host_headers",
        hdrs = SHARED_HEADERS,
        includes = ["..", "gen"],
        deps = ["@chromium_dxc//:headers", "@chromium_dawn//:dxc_build_headers"],
    )
    for original, library in LIBRARIES.items():
        cc_library = host_cc_library if "(//build/toolchain/linux:" in original else platform_cc_library
        include_options = ["-I" + Label("@chromium_dxc//:headers").workspace_root + "/" + path for path in library.get("dxc_include_dirs", [])]
        c_sources = [source for source in library["srcs"] if source.endswith(".c")]
        common = dict(
            hdrs = library["hdrs"],
            includes = library["includes"],
            local_defines = library["defines"],
            linkopts = library["linkopts"],
            linkstatic = True,
            alwayslink = library["kind"] == "source_set",
            deps = ([":dawn_dxc_host_headers"] if "(//build/toolchain/linux:" in original else [":dawn_native_headers"]) + library["deps"],
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
        common["deps"] = common["deps"] + resources
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
                copts = library["c_copts"] + include_options,
                **common
            )
            common["deps"] = common["deps"] + [":" + library["name"] + "_c"]
        sources = [source for source in library["srcs"] if source not in c_sources]
        if library["kind"] == "shared_library":
            headers = common.pop("hdrs")
            common.pop("alwayslink")
            cc_binary(
                name = "dxcompiler.dll",
                srcs = sources + headers,
                copts = library["copts"] + include_options,
                linkshared = True,
                win_def_file = "@chromium_dxc//:tools/clang/tools/dxcompiler/DXCompiler.def",
                **common
            )
            platform_cc_library(
                name = library["name"],
                data = [":dxcompiler.dll"],
                deps = [":dawn_native_headers"],
            )
        elif library["kind"] == "executable":
            sources = sources + common.pop("hdrs")
            common.pop("alwayslink")
            cc_binary(
                name = library["name"],
                srcs = sources,
                copts = library["copts"] + include_options,
                **common
            )
        else:
            cc_library(
                name = library["name"],
                srcs = sources,
                copts = library["copts"] + include_options,
                **common
            )
    native.alias(
        name = "dawn_native_library",
        actual = ":" + LIBRARIES["//third_party/dawn/src/dawn/native:static"]["name"],
    )
