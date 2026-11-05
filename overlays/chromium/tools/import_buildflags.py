#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Port captured buildflag generators to declared native Bazel actions."""

import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = frozenset((
    '//build/write_buildflag_header.py',
    '//base/allocator/partition_allocator/src/partition_alloc/write_buildflag_header.py',
))


def main():
    graph = json.loads(gzip.decompress(Path(sys.argv[1]).read_bytes()))
    records = []
    for label, target in sorted(graph['targets'].items()):
        script = target.get('script', '')
        if script not in SCRIPTS:
            continue
        if target['type'] != 'action':
            raise ValueError(f'unsupported buildflag action: {label}')
        if len(target['outputs']) != 1:
            raise ValueError(f'buildflag output count: {label}')
        output = target['outputs'][0].removeprefix('//out/bazel-import/')
        if output == target['outputs'][0]:
            raise ValueError(f'output outside build directory: {label}')
        name = 'flags_' + hashlib.sha256(label.encode()).hexdigest()[:16]
        records.append((name, label, script, target['args'], output,
                        target['response_file_contents']))
    lines = [
        '"""Generated from pinned Linux x86_64 graph; run tools/import_buildflags.py."""',
        '',
        'load("@rules_cc//cc:cc_library.bzl", "cc_library")',
        'load(":python_action.bzl", "chromium_python_action")',
        '',
        'def native_buildflags(name):',
        '    """Declare pinned Chromium buildflag actions.',
        '',
        '    Args:',
        '        name: Filegroup collecting generated headers.',
        '    """',
    ]
    for name, label, script, args, output, response in records:
        package, filename = script.rsplit('/', 1)
        source_label = package + ':' + filename
        lines.extend([
            '    chromium_python_action(',
            f'        name = {json.dumps(name)},',
            f'        srcs = {{{json.dumps(source_label)}: {json.dumps(script[2:])}}},',
            f'        script = {json.dumps(script[2:])},',
            f'        args = {json.dumps(args)},',
            f'        outs = {{{json.dumps(output)}: {json.dumps(output)}}},',
            f'        response_file_contents = {json.dumps(response)},',
            '    )',
        ])
        if label == '//base:debugging_buildflags':
            lines.extend([
                '    cc_library(',
                '        name = "debugging_buildflags",',
                f'        hdrs = [":{name}"],',
                '        includes = ["gen"],',
                '        deps = ["//build:buildflag"],',
                '    )',
            ])
    lines.extend([
        '    native.filegroup(',
        '        name = name,',
        '        srcs = ' + json.dumps([':' + r[0] for r in records]) + ',',
        '    )',
    ])
    path = ROOT / 'bcr/overlay/native/buildflags.bzl'
    path.write_text('\n'.join(lines) + '\n')
    print(f'Imported {len(records)} native buildflag actions')


if __name__ == '__main__':
    main()
