"""Run Chromium's original CXX wrapper with native compiled tools."""

load(":python_action.bzl", "chromium_python_action")
load(":tool_inputs.bzl", "chromium_tool_inputs")

def native_cxx_tools(name):
    """Expose native tools and query the pinned compiler's target configuration.

    Args:
        name: Compiled tool output group.
    """
    chromium_tool_inputs(
        name = "rustc_inputs",
        tool = "//native/rust:rustc_tool",
        logical_path = "third_party/rust-toolchain/bin/rustc",
    )
    chromium_tool_inputs(
        name = "cxxbridge_inputs",
        tool = "//native/rust:cxxbridge",
        logical_path = "out/bazel-import/clang_x64_for_rust_host_build_tools/cxxbridge",
    )
    chromium_python_action(
        name = "rustc_cfg",
        srcs = {"//build:rust/gni_impl/rustc_print_cfg.py": "build/rust/gni_impl/rustc_print_cfg.py"},
        outs = {"gen/build/rust/gni_impl/rustc-print-cfg-x86_64-unknown-linux-gnu.txt": "gen/build/rust/gni_impl/rustc-print-cfg-x86_64-unknown-linux-gnu.txt"},
        script = "build/rust/gni_impl/rustc_print_cfg.py",
        args = ["--rust-prefix", "../../third_party/rust-toolchain/bin", "--target", "x86_64-unknown-linux-gnu", "--output-path", "gen/build/rust/gni_impl/rustc-print-cfg-x86_64-unknown-linux-gnu.txt"],
        deps = [":rustc_inputs"],
    )

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
            "gen/build/rust/gni_impl/rustc-print-cfg-x86_64-unknown-linux-gnu.txt",
            "../../" + logical_source,
            "--",
        ],
        deps = [":cxxbridge_inputs", ":rustc_cfg"],
        **kwargs
    )
