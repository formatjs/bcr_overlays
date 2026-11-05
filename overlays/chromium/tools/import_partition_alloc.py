#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Import PartitionAlloc's pinned Linux sources and native compiler settings."""

import gzip
import json
from pathlib import Path
import sys

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
    for name in TARGETS:
        target = graph['targets'][LABEL + name]
        for field in ('cflags', 'cflags_cc', 'include_dirs'):
            if graph['pool'][target[field]['pool']] != unpack(field):
                raise ValueError(f'per-target compiler configuration needs mapping: {name} {field}')
    flags = []
    compiler_flags = iter(unpack('cflags') + unpack('cflags_cc'))
    for flag in compiler_flags:
        if flag == '-Xclang':
            argument = next(compiler_flags)
            if argument not in ('-fmodule-file-home-is-cwd', '-fmodules-local-submodule-visibility'):
                raise ValueError(f'unmapped Clang frontend option: {argument}')
            continue
        if (flag == '-Werror' or flag == '-nostdinc++' or
                flag.startswith(('-fcrash-diagnostics-dir=', '--warning-suppression-mappings=',
                                 '--target=', '--sysroot=', '-isystem', '-fmodules',
                                 '-fno-implicit-module', '-fbuiltin-module-map',
                                 '-fmodule-map-file='))):
            continue
        flags.append(flag)
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
