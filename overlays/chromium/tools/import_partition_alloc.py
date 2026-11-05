#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Import PartitionAlloc's pinned Linux sources and native compiler settings."""

import gzip
import json
from pathlib import Path
import sys

from import_mojo_runtime import compiler_configuration

ROOT = Path(__file__).resolve().parents[1]
PREFIX = '//base/allocator/partition_allocator/src/partition_alloc/'
LABEL = PREFIX[:-1] + ':'
TARGETS = ['allocator_base', 'allocator_core', 'allocator_shim', 'raw_ptr']


def main():
    graph = json.loads(gzip.decompress(Path(sys.argv[1]).read_bytes()))
    source = Path(sys.argv[2])
    records = {}
    for name in TARGETS:
        target = graph['targets'][LABEL + name]
        if target['type'] != 'static_library':
            raise ValueError(f'unexpected native target type: {name}')
        files = target['sources']
        if any(not p.startswith(PREFIX) for p in files):
            raise ValueError(f'source outside PartitionAlloc: {name}')
        records[name] = [p.removeprefix(PREFIX) for p in files if p.endswith('.cc')]
        for path in files:
            if Path(path).suffix not in ('.cc', '.h', '.inc'):
                raise ValueError(f'unmapped source language: {path}')
            if not (source / path[2:]).is_file():
                raise ValueError(f'missing source: {path}')
    directory = source / PREFIX[2:]
    headers = sorted(str(p.relative_to(directory)) for p in directory.rglob('*')
                     if p.is_file() and p.suffix in ('.h', '.inc'))
    base = graph['targets'][LABEL + 'allocator_base']
    unpack = lambda key: graph['pool'][base[key]['pool']]
    options = {}
    for name in TARGETS:
        target = graph['targets'][LABEL + name]
        if graph['pool'][target['include_dirs']['pool']] != unpack('include_dirs'):
            raise ValueError(f'per-target include directories need mapping: {name}')
        options[name], _ = compiler_configuration(graph, target)
    flags = options if any(value != options['allocator_base'] for value in options.values()) else options['allocator_base']
    defines = [s for s in unpack('defines') if not s.startswith(
        ('IS_PARTITION_ALLOC_BASE_IMPL', 'CR_LIBCXX_REVISION=', 'CR_SYSROOT_KEY=', 'USE_LIBCXX_MODULES'))]
    data = {'SOURCES': records, 'HEADERS': headers, 'COPTS': flags, 'DEFINES': defines}
    output = ROOT / 'bcr/overlay/base/allocator/partition_allocator/src/partition_alloc'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'sources.bzl').write_text(
        '"""Generated from pinned Linux graph; run tools/import_partition_alloc.py."""\n\n' +
        '\n\n'.join(key + ' = ' + json.dumps(value, indent=4) for key, value in data.items()) + '\n')
    print(f'Imported {sum(map(len, records.values()))} C++ sources, {len(headers)} headers')


if __name__ == '__main__':
    main()
