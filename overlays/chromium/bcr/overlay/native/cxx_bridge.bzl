"""Run Chromium's original CXX wrapper with native compiled tools."""

load(":python_action.bzl", "ChromiumFilesInfo", "ChromiumGeneratedFilesInfo", "chromium_python_action")
load(":tool_inputs.bzl", "chromium_tool_inputs")

def _rustc_cfg_impl(ctx):
    logical = "gen/build/rust/gni_impl/bazel-rustc-print-cfg.txt"
    output = ctx.actions.declare_file(logical)
    rust = ctx.attr._rust[platform_common.ToolchainInfo]
    ctx.actions.run(
        executable = rust.rustc,
        arguments = ["--print=cfg=" + output.path, "--target=" + str(rust.target_flag_value)],
        inputs = rust.all_files,
        outputs = [output],
        mnemonic = "ChromiumRustcCfg",
    )
    mappings = depset([(output, "out/bazel-import/" + logical)])
    return [
        DefaultInfo(files = depset([output])),
        ChromiumFilesInfo(mappings = mappings),
        ChromiumGeneratedFilesInfo(mappings = mappings),
    ]

_rustc_cfg = rule(
    implementation = _rustc_cfg_impl,
    attrs = {
        "_rust": attr.label(default = Label("@rules_rust//rust/toolchain:current_rust_toolchain")),
    },
)

def native_cxx_tools(name):
    """Expose native tools and query the pinned compiler's target configuration.

    Args:
        name: Compiled tool output group.
    """
    chromium_tool_inputs(
        name = "cxxbridge_inputs",
        tool = "//native/rust:cxxbridge",
        logical_path = "out/bazel-import/clang_x64_for_rust_host_build_tools/cxxbridge",
    )
    _rustc_cfg(name = "rustc_cfg")

    native.filegroup(name = name, srcs = [":cxxbridge_inputs", ":rustc_cfg"])

def chromium_cxx_bridge(name, src, logical_source, **kwargs):
    """Generate original CXX header and source with declared tool prerequisites.

    Args:
        name: Generator target.
        src: Rust bridge file.
        logical_source: Chromium-relative path.
        **kwargs: Common rule attributes.
    """
    chromium_python_action(
        name = name,
        srcs = {
            src: logical_source,
            "//:third_party/rust/cxx/chromium_integration/run_cxxbridge.py": "third_party/rust/cxx/chromium_integration/run_cxxbridge.py",
            "//build:action_helpers.py": "build/action_helpers.py",
            "//build:gn_helpers.py": "build/gn_helpers.py",
        },
        outs = {"gen/" + logical_source + extension: "gen/" + logical_source + extension for extension in [".h", ".cc"]},
        script = "third_party/rust/cxx/chromium_integration/run_cxxbridge.py",
        args = [
            "--exe",
            "clang_x64_for_rust_host_build_tools/cxxbridge",
            "--header",
            "gen/" + logical_source + ".h",
            "--cc",
            "gen/" + logical_source + ".cc",
            "--rustc-print-cfg-path",
            "gen/build/rust/gni_impl/bazel-rustc-print-cfg.txt",
            "../../" + logical_source,
            "--",
        ],
        deps = [":cxxbridge_inputs", ":rustc_cfg"],
        **kwargs
    )
