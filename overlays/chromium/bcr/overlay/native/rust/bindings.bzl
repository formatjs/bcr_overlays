"""Preserve Chromium's bindings.rs wrapper around native BCR bindgen."""

load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")
load("@rules_rs//rs:rules_rust_bindgen.bzl", "rust_bindgen")
load("@rules_rs//rs:rust_library.bzl", "rust_library")
load("@rules_rust//rust:rust_common.bzl", "BuildInfo")

def _directory_impl(ctx):
    output = ctx.actions.declare_directory(ctx.label.name)
    arguments = [ctx.file.src.path, output.path]
    if ctx.attr.output_name != "bindings.rs":
        arguments.append(ctx.attr.output_name)
    ctx.actions.run(
        executable = ctx.attr._tool[DefaultInfo].files_to_run,
        inputs = [ctx.file.src],
        outputs = [output],
        arguments = arguments,
        mnemonic = "ChromiumBindgenLayout",
    )
    return [
        DefaultInfo(files = depset([output])),
        ctx.attr.cc_lib[CcInfo],
        BuildInfo(out_dir = output, compile_data = depset([output]), dep_env = None, rustc_env = None, flags = None, linker_flags = None, link_search_paths = None),
    ]

_bindings_directory = rule(
    implementation = _directory_impl,
    attrs = {
        "src": attr.label(allow_single_file = True),
        "cc_lib": attr.label(providers = [CcInfo], mandatory = True),
        "output_name": attr.string(default = "bindings.rs"),
        "_tool": attr.label(default = Label("//native/rust:copy_bindings"), executable = True, cfg = "exec"),
    },
)

def chromium_bindgen_library(name, header, cc_lib, bindgen_flags = None, clang_flags = None, cpp = True, deps = None, **kwargs):
    """Generate bindings and compile Chromium's original namespace wrapper.

    Args:
        name: Rust crate target.
        header: Original C++ header.
        cc_lib: Header owner and link dependency.
        bindgen_flags: Original binding filters and options.
        clang_flags: Header language and parsing options.
        cpp: Reexport the C++ namespace from Chromium's wrapper.
        deps: Additional Rust crate dependencies.
        **kwargs: Rust crate settings.
    """
    rust_bindgen(
        name = name + "_generator",
        header = header,
        cc_lib = cc_lib,
        bindgen_flags = ["--enable-cxx-namespaces", "--no-layout-tests"] if bindgen_flags == None else bindgen_flags,
        clang_flags = ["-x", "c++", "-std=c++20"] if clang_flags == None else clang_flags,
    )
    _bindings_directory(name = name + "_bindings", src = ":" + name + "_generator", cc_lib = cc_lib)
    rust_library(
        name = name,
        srcs = ["//build:rust/bindings.rs"],
        crate_root = "//build:rust/bindings.rs",
        rustc_flags = ["--cfg=cpp"] if cpp else [],
        deps = [":" + name + "_bindings"] + (deps or []),
        **kwargs
    )

def chromium_bindgen_inputs(name, header, cc_lib, bindgen_flags, clang_flags, output_name):
    """Stage native bindings at the filename expected by the original Rust crate."""
    rust_bindgen(
        name = name + "_generator",
        header = header,
        cc_lib = cc_lib,
        bindgen_flags = bindgen_flags,
        clang_flags = clang_flags,
    )
    _bindings_directory(name = name, src = ":" + name + "_generator", output_name = output_name, cc_lib = cc_lib)
