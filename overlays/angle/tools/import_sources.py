#!/usr/bin/env python3
"""Import the pinned Linux translator source lists; never runs during a build."""

import argparse
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read_list(source, name):
    match = re.search(r"(?m)^" + re.escape(name) + r"\s*=\s*(?:(\w+)\s*\+\s*)?\[(.*?)\]", source, re.S)
    if not match:
        raise ValueError(f"missing literal source list: {name}")
    values = ast.literal_eval("[" + match[2] + "]")
    if not all(isinstance(value, str) for value in values):
        raise ValueError(f"nonliteral source list: {name}")
    return (read_list(source, match[1]) if match[1] else []) + values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    compiler = (args.source / "src/compiler.gni").read_text()
    common = (args.source / "src/libGLESv2.gni").read_text()
    groups = {
        "PUBLIC": read_list(common, "libangle_includes") + read_list(compiler, "angle_translator_exported_headers"),
        "COMMON": read_list(common, "libangle_common_sources") + [
            "src/common/backtrace_utils_noop.cpp",
            "src/common/system_utils_linux.cpp",
            "src/common/system_utils_posix.cpp",
        ],
        "SHADER_STATE": read_list(common, "libangle_common_shader_state_sources"),
        "XXHASH": read_list(common, "xxhash_sources"),
        "PREPROCESSOR": read_list(compiler, "angle_preprocessor_sources"),
        "TRANSLATOR": sum((read_list(compiler, name) for name in (
            "angle_translator_exported_headers",
            "angle_translator_sources",
            "angle_translator_essl_symbol_table_sources",
            "angle_translator_essl_sources",
            "angle_translator_glsl_sources",
            "angle_translator_glsl_base_sources",
            "angle_translator_glsl_and_vulkan_base_sources",
        )), []) + ["src/common/spirv/spirv_types.h"],
    }
    result = ['"""Linux ESSL/GLSL lists from pinned src/compiler.gni and src/libGLESv2.gni."""\n']
    for name, paths in groups.items():
        for path in paths:
            if not (args.source / path).is_file():
                raise ValueError(f"missing source: {path}")
        for kind, suffixes in (("SRCS", (".c", ".cc", ".cpp")), ("HDRS", (".h", ".inc"))):
            selected = sorted({path for path in paths if path.endswith(suffixes)})
            result.append(f"{name}_{kind} = [\n" + "".join(f"    {json.dumps(path)},\n" for path in selected) + "]\n")
    (ROOT / "bcr/overlay/angle_sources.bzl").write_text("\n".join(result))


if __name__ == "__main__":
    main()
