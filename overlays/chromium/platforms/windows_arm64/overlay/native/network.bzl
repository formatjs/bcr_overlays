"""Captured Windows network closure and Linux host generators."""

load("@rules_cc//cc:cc_binary.bzl", "cc_binary")
load("@rules_cc//cc:cc_library.bzl", _cc_library = "cc_library")
load(":host_support.bzl", cc_library = "platform_cc_library")
load(":network_sources.bzl", "ACTIONS", "LIBRARIES", "SHARED_HEADERS", "TOOLS")
load(":protobuf_config.bzl", "chromium_protobuf_library")
load(":python_action.bzl", "chromium_python_action")
load(":tool_inputs.bzl", "chromium_tool_inputs")

def native_network():
    chromium_protobuf_library(name = "protobuf_full_runtime", dep = "@protobuf//:protobuf")
    _cc_library(
        name = "network_headers",
        hdrs = SHARED_HEADERS + [":all_buildflags"] + native.glob(["network_forwarders/**/*.h"]),
        includes = ["..", "gen", "network_forwarders"],
    )
    for name, tool in TOOLS.items():
        chromium_tool_inputs(name = name, **tool)
    for action in ACTIONS:
        chromium_python_action(**action)
    for original, library in LIBRARIES.items():
        host = "(//build/toolchain/linux:" in original
        common = dict(
            copts = library["copts"],
            local_defines = library["defines"],
            linkopts = library["linkopts"],
            linkstatic = True,
            deps = [":network_headers"] + library["deps"],
        )
        if library["kind"] == "executable":
            cc_binary(
                name = library["name"],
                srcs = library["srcs"] + library["hdrs"],
                **common
            )
            continue
        rule = _cc_library if host else cc_library
        rule(
            name = library["name"],
            srcs = library["srcs"],
            hdrs = library["hdrs"],
            includes = library["includes"],
            alwayslink = library["kind"] == "source_set",
            **common
        )
    for name, original in {"net": "//net:net", "sql": "//sql:sql"}.items():
        native.alias(name = name, actual = ":" + LIBRARIES[original]["name"])
