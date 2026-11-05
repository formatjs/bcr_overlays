#!/usr/bin/env python3
"""Import Chromium ICU's pinned, explicit GN source lists outside the build."""

import argparse
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    text = (args.source / "sources.gni").read_text()
    result = ['"""Source lists from Chromium ICU 74.2 sources.gni."""\n']
    for group, names, prefix in [
        ("COMMON", ["icuuc_sources", "icuuc_public"], "source/common/"),
        ("I18N", ["icu18n_sources", "icu18n_public"], "source/i18n/"),
    ]:
        paths = set()
        for name in names:
            match = re.search(r"(?m)^" + name + r"\s*=\s*\[(.*?)\]", text, re.S)
            if not match:
                raise ValueError(f"missing source list: {name}")
            paths.update(ast.literal_eval("[" + match[1] + "]"))
        for path in paths:
            if not path.startswith(prefix) or not (args.source / path).is_file():
                raise ValueError(f"unexpected source: {path}")
        for kind, suffixes in [("SRCS", (".cpp", ".cc")), ("HDRS", (".h",))]:
            selected = sorted(path.removeprefix(prefix) for path in paths if path.endswith(suffixes))
            result.append(group + "_" + kind + " = [\n" + "".join("    " + json.dumps(path) + ",\n" for path in selected) + "]\n")
    (ROOT / "bcr/overlay/icu_sources.bzl").write_text("\n".join(result))


if __name__ == "__main__":
    main()
