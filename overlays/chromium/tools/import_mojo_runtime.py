#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Import original Linux Mojo core, bindings and system source configurations."""
import argparse
import gzip
import json
from pathlib import Path

from import_base import replace_block, sort_archive_files

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    'unix_address': '//net:net',
    'features': '//mojo/core/embedder:features',
    'platform': '//mojo/public/cpp/platform:platform',
    'c_system': '//mojo/public/c/system:system',
    'core': '//mojo/core:impl_for_embedder',
    'embedder': '//mojo/core/embedder:embedder',
    'cpp_system': '//mojo/public/cpp/system:system',
    'ipc_messages': '//ipc:message_support',
    'bindings_base': '//mojo/public/cpp/bindings:bindings_base',
    'bindings_control': '//mojo/public/interfaces/bindings:bindings',
    'bindings_shared': '//mojo/public/interfaces/bindings:bindings_shared_cpp_sources',
    'cpp_bindings': '//mojo/public/cpp/bindings:bindings',
    'interface_provider': '//services/service_manager/public/mojom:mojom',
    'base_values': '//mojo/public/cpp/base:base',
    'base_shared': '//mojo/public/mojom/base:base_shared_cpp_sources',
    'base_traits_shared': '//mojo/public/cpp/base:shared_typemap_traits',
    'base_traits': '//mojo/public/cpp/base:typemap_traits',
    'base_types': '//mojo/public/mojom/base:base',
}


def compiler_configuration(graph, target):
    unpack = lambda value: graph['pool'][value['pool']] if isinstance(value, dict) else value
    flags = []
    iterator = iter(unpack(target['cflags']) + unpack(target['cflags_cc']))
    for flag in iterator:
        if flag == '-Xclang':
            argument = next(iterator)
            if argument not in ('-fmodule-file-home-is-cwd', '-fmodules-local-submodule-visibility'):
                raise ValueError(f'unmapped frontend flag: {argument}')
            continue
        if flag in ('-Werror', '-nostdinc++') or flag.startswith((
                '-fcrash-diagnostics-dir=', '--warning-suppression-mappings=', '--target=',
                '--sysroot=', '-isystem', '-fmodules', '-fno-implicit-module',
                '-fbuiltin-module-map', '-fmodule-map-file=')):
            continue
        flags.append(flag)
    defines = [value for value in unpack(target['defines']) if not value.startswith((
        'CR_LIBCXX_REVISION=', 'CR_SYSROOT_KEY=', 'USE_LIBCXX_MODULES'))]
    return flags, defines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--source-root', type=Path, required=True)
    args = parser.parse_args()
    graph = json.loads(gzip.decompress(args.graph.read_bytes()))
    sources, options, defines = {}, {}, {}
    for name, label in TARGETS.items():
        target = graph['targets'][label]
        sources[name] = [path.removeprefix('//out/bazel-import/').removeprefix('//')
                         for path in target['sources'] if path.endswith('.cc')]
        options[name], defines[name] = compiler_configuration(graph, target)
    sources['unix_address'] = ['net/base/sockaddr_storage.cc', 'net/base/sockaddr_util_posix.cc']
    sources['interface_provider'] = [
        'gen/services/service_manager/public/mojom/interface_provider.mojom.cc',
        'gen/services/service_manager/public/mojom/interface_provider.mojom-shared.cc',
    ]
    headers = sorted(str(path.relative_to(args.source_root))
                     for directory in ['mojo', 'ipc']
                     for path in (args.source_root / directory).rglob('*')
                     if path.is_file() and path.suffix in ('.h', '.inc'))
    headers += ['net/base/net_export.h', 'net/base/sockaddr_storage.h', 'net/base/sockaddr_util_posix.h']
    schemas = ['gen/mojo/public/interfaces/bindings/' + name for name in
               ['interface_control_messages', 'native_struct', 'pipe_control_messages']]
    schemas.append('gen/services/service_manager/public/mojom/interface_provider')
    schemas.extend(path.removesuffix('.mojom.cc') for path in sources['base_types'])
    generated = sorted({path.removeprefix('//out/bazel-import/')
                        for target in graph['targets'].values() for path in target.get('outputs', [])
                        if path.endswith('.h') and any(path.startswith('//out/bazel-import/' + schema + '.mojom') for schema in schemas)})
    inputs = set(headers) | {path for values in sources.values() for path in values}
    if any(not (args.source_root / path).is_file() for path in inputs if not path.startswith('gen/')):
        raise ValueError('missing Mojo runtime source')
    overlay = ROOT / 'bcr/overlay'
    replace_block(overlay / 'BUILD.bazel', '# BEGIN GENERATED MOJO RUNTIME INPUTS',
                  '# END GENERATED MOJO RUNTIME INPUTS', 'exports_files(' + json.dumps(sorted(path for path in inputs if not path.startswith('gen/')), indent=4) + ')')
    data = {'SOURCES': sources, 'HEADERS': headers, 'GENERATED_HEADERS': generated, 'COPTS': options, 'DEFINES': defines}
    (overlay / 'native/mojo_runtime_sources.bzl').write_text('"""Generated by tools/import_mojo_runtime.py."""\n\n' +
        '\n\n'.join(key + ' = ' + json.dumps(value, indent=4) for key, value in data.items()) + '\n')
    module = ROOT / 'MODULE.bazel'
    text = module.read_text()
    for filename in ['mojo_runtime.bzl', 'mojo_runtime_sources.bzl']:
        line = f'        "native/{filename}": "//bcr/overlay/native:{filename}",\n'
        if line not in text:
            marker = text.index('        "native/BUILD.bazel":')
            text = text[:marker] + line + text[marker:]
    module.write_text(sort_archive_files(text))
    print(f'Imported {sum(map(len, sources.values()))} Mojo/platform C++ sources and {len(headers)} headers')


if __name__ == '__main__':
    main()
