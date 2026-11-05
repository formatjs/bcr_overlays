"""Blink modules and their original code generators."""

load("@rules_cc//cc:cc_library.bzl", "cc_library")
load(":blink_modules_sources.bzl", "ACTIONS", "LIBRARIES", "SHARED_HEADERS", "TOOLS")
load(":python_action.bzl", "chromium_python_action")
load(":tool_inputs.bzl", "chromium_tool_inputs")

def native_blink_modules():
    for name, tool in TOOLS.items():
        chromium_tool_inputs(name = name, **tool)
    for action in ACTIONS:
        chromium_python_action(**action)
    cc_library(
        name = "blink_modules_headers",
        hdrs = SHARED_HEADERS + [":all_buildflags"] + native.glob(["blink_modules_forwarders/**/*.h"], allow_empty = True),
        includes = ["..", "gen", "blink_modules_forwarders"],
        deps = [":blink_core_headers", ":libxslt"],
    )
    for original, library in LIBRARIES.items():
        c_sources = [p for p in library["srcs"] if p.endswith(".c")]
        common = dict(
            hdrs = library["hdrs"],
            includes = library["includes"],
            local_defines = library["defines"],
            linkopts = library["linkopts"],
            linkstatic = True,
            alwayslink = library["kind"] == "source_set",
            deps = [":blink_modules_headers"] + library["deps"],
        )
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
            srcs = [p for p in library["srcs"] if p not in c_sources],
            copts = library["copts"],
            **common
        )
    native.alias(
        name = "blink_modules",
        actual = ":" + LIBRARIES["//third_party/blink/renderer/modules:modules"]["name"],
    )
    native.filegroup(
        name = "blink_modules_assets",
        srcs = [":" + action["name"] for action in ACTIONS],
    )
