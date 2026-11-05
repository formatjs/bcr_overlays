#!/usr/bin/env python3
"""Import Chromium's pinned Perfetto runtime build flags."""
import argparse
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def flags(path):
    graph = json.loads(gzip.decompress(path.read_bytes()))
    values = graph['targets']['//third_party/perfetto/gn:gen_buildflags']['response_file_contents']
    if values[0] != '--flags' or 'PERFETTO_CHROMIUM_BUILD=true' not in values:
        raise ValueError('expected Chromium runtime flags')
    return values[1:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--windows-graph', type=Path)
    args = parser.parse_args()
    value = json.dumps(flags(args.graph), indent=4)
    if args.windows_graph:
        value = 'select({\n"@platforms//os:windows": ' + json.dumps(
            flags(args.windows_graph), indent=4) + ',\n"//conditions:default": ' + value + ',\n})'
    (ROOT / 'bcr/overlay/bazel/chromium_flags.bzl').write_text(
        '"""Generated from Chromium 142 native graph; tools/import_chromium_flags.py."""\n\n'
        + 'CHROMIUM_FLAGS = ' + value + '\n')


if __name__ == '__main__':
    main()
