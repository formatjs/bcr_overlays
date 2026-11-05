#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Port GN-time configuration files as native Bazel write actions."""

import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    graph = json.loads(gzip.decompress(Path(sys.argv[1]).read_bytes()))
    outputs = {}
    for path, contents in sorted(graph['generated_files'].items()):
        name = path.removeprefix('//out/bazel-import/')
        if name == path or '$SOURCE_ROOT' in contents or '$LLVM_ROOT' in contents:
            raise ValueError(f'nonportable generated file: {path}')
        outputs[name] = contents
    (ROOT / 'bcr/overlay/native/generated_files.bzl').write_text(
        '\n'.join([
            '"""Pinned GN-time metadata; regenerate with tools/import_generated_files.py."""',
            '',
            '_FILES = ' + json.dumps(outputs, indent=4),
            '',
            'CAPTURED_FILES = _FILES',
            '',
            'def _generated_files_impl(ctx):',
            '    outputs = []',
            '    for output, contents in zip(ctx.outputs.outs, _FILES.values()):',
            '        ctx.actions.write(output, contents)',
            '        outputs.append(output)',
            '    return [DefaultInfo(files = depset(outputs))]',
            '',
            '_generated_files = rule(',
            '    implementation = _generated_files_impl,',
            '    attrs = {"outs": attr.output_list(mandatory = True)},',
            ')',
            '',
            'def captured_generated_files(name):',
            '    """Declare configuration outputs.',
            '',
            '    Args:',
            '        name: Target collecting pinned configuration files.',
            '    """',
            '    _generated_files(name = name, outs = _FILES.keys())',
            '',
        ]))
    print(f'Imported {len(outputs)} native metadata write actions')


if __name__ == '__main__':
    main()
