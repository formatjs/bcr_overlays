"""Use one native GLib family across Chromium and desktop DSOs."""

load("@rules_cc//cc:cc_binary.bzl", "cc_binary")
load("@rules_cc//cc:cc_import.bzl", "cc_import")
load("@rules_cc//cc:cc_library.bzl", "cc_library")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

def _linkage_impl(ctx):
    runtime = ctx.attr.runtime[DefaultInfo]
    runfiles = ctx.runfiles(transitive_files = runtime.files).merge(runtime.default_runfiles)
    runfiles = runfiles.merge(ctx.attr.library[DefaultInfo].default_runfiles)
    return [
        CcInfo(
            compilation_context = ctx.attr.library[CcInfo].compilation_context,
            linking_context = ctx.attr.shared[CcInfo].linking_context,
        ),
        DefaultInfo(files = runtime.files, runfiles = runfiles),
    ]

_linkage = rule(
    implementation = _linkage_impl,
    attrs = {
        "library": attr.label(providers = [CcInfo], mandatory = True),
        "shared": attr.label(providers = [CcInfo], mandatory = True),
        "runtime": attr.label(mandatory = True),
    },
)

def shared_glib_library(name, soname, **kwargs):
    visibility = kwargs.get("visibility")
    cc_library(
        name = name + "_static",
        alwayslink = select({"@platforms//os:linux": True, "//conditions:default": False}),
        **kwargs
    )
    compatible = select({"@platforms//os:linux": [], "//conditions:default": ["@platforms//:incompatible"]})
    cc_binary(
        name = soname,
        deps = [":" + name + "_static"],
        linkshared = True,
        linkstatic = True,
        linkopts = ["-Wl,-soname," + soname],
        target_compatible_with = compatible,
        visibility = visibility,
    )
    cc_import(
        name = name + "_shared_import",
        shared_library = ":" + soname,
        target_compatible_with = compatible,
    )
    _linkage(
        name = name,
        library = ":" + name + "_static",
        shared = select({"@platforms//os:linux": ":" + name + "_shared_import", "//conditions:default": ":" + name + "_static"}),
        runtime = select({"@platforms//os:linux": ":" + soname, "//conditions:default": ":" + name + "_static"}),
        visibility = visibility,
    )
