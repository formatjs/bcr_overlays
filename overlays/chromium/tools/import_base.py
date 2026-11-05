#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Import Chromium's complete Linux base library and support sources."""
import argparse
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = {
    'base_static': '//base:base_static',
    'dwarf_helpers': '//base:dwarf_helpers',
    'cityhash_v103': '//base/third_party/cityhash_v103:cityhash_v103',
    'symbolize': '//base/third_party/symbolize:symbolize',
    'xdg_user_dirs': '//base/third_party/xdg_user_dirs:xdg_user_dirs',
    'base': '//base:base',
    'base_i18n': '//base:i18n',
}


def starlark_literal(value):
    """Render JSON-shaped metadata without changing keywords inside strings."""
    keywords = {'true': 'True', 'false': 'False', 'null': 'None'}
    return re.sub(r'("(?:\\.|[^"\\])*")|\b(true|false|null)\b',
                  lambda match: match[1] if match[1] is not None else keywords[match[2]],
                  json.dumps(value, indent=4))


def replace_block(path, begin, end, block):
    text = path.read_text()
    if begin in text:
        before, rest = text.split(begin, 1)
        _, after = rest.split(end, 1)
        text = before + begin + '\n' + block + '\n' + end + after
    else:
        text += '\n' + begin + '\n' + block + '\n' + end + '\n'
    path.write_text(text)


def sort_archive_files(text):
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == 'files = {')
    end = next(index for index in range(start + 1, len(lines)) if lines[index].strip() == '},')
    entries = lines[start + 1:end]
    if any(not line.strip().startswith('"') for line in entries):
        raise ValueError('unsupported archive file mapping format')
    lines[start + 1:end] = sorted(entries)
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    args = parser.parse_args()
    graph = json.loads(gzip.decompress(args.graph.read_bytes()))
    overlay = ROOT / 'bcr/overlay'
    unpack = lambda value: graph['pool'][value['pool']] if isinstance(value, dict) and 'pool' in value else value
    inputs, sources, options, definitions = set(), {}, {}, {}
    for name, label in SUPPORT.items():
        target = graph['targets'][label]
        if target['type'] not in ('static_library', 'source_set'):
            raise ValueError(f'unmapped base target type: {label}')
        for path in target['sources']:
            if Path(path).suffix not in ('.cc', '.c', '.h', '.inc'):
                raise ValueError(f'unmapped base source language: {path}')
        sources[name] = [path[2:] for path in target['sources'] if path.endswith(('.cc', '.c'))]
        inputs.update(sources[name])
        flags = []
        iterator = iter(unpack(target['cflags']) + unpack(target['cflags_cc']))
        for flag in iterator:
            if flag == '-Xclang':
                argument = next(iterator)
                if argument not in ('-fmodule-file-home-is-cwd', '-fmodules-local-submodule-visibility'):
                    raise ValueError(f'unmapped frontend flag: {argument}')
                continue
            if flag == '-Werror' or flag == '-nostdinc++' or flag.startswith((
                    '-fcrash-diagnostics-dir=', '--warning-suppression-mappings=', '--target=',
                    '--sysroot=', '-isystem', '-fmodules', '-fno-implicit-module',
                    '-fbuiltin-module-map', '-fmodule-map-file=')):
                continue
            flags.append(flag)
        options[name] = flags
        definitions[name] = [value for value in unpack(target['defines']) if not value.startswith((
            'CR_LIBCXX_REVISION=', 'CR_SYSROOT_KEY=', 'USE_LIBCXX_MODULES'))]
    headers = []
    for path in sorted((args.source_root / 'base').rglob('*')):
        if not path.is_file() or path.suffix not in ('.h', '.inc'):
            continue
        relative = path.relative_to(args.source_root)
        owner = (overlay / relative).parent
        while owner != overlay and not (owner / 'BUILD.bazel').is_file():
            owner = owner.parent
        if owner == overlay:
            headers.append(str(relative))
    inputs.update(headers)
    inputs.update(['base/logging/rust_logger.rs', 'base/write_build_date_header.py',
                   'base/check_version_internal.h.in', 'chrome/VERSION'])
    inputs.update(str(path.relative_to(args.source_root)) for path in
                  (args.source_root / 'base/tracing/protos').glob('*.proto'))
    if any(not (args.source_root / path).is_file() for path in inputs):
        raise ValueError('missing base source input')
    replace_block(overlay / 'BUILD.bazel', '# BEGIN GENERATED BASE INPUTS', '# END GENERATED BASE INPUTS',
                  'exports_files(' + json.dumps(sorted(inputs), indent=4) + ')')
    replace_block(overlay / 'build/BUILD.bazel', '# BEGIN GENERATED BASE INPUTS', '# END GENERATED BASE INPUTS',
                  'exports_files(["util/version.py", "util/android_chrome_version.py", "util/LASTCHANGE.dummy"])')
    data = {'SOURCES': sources, 'HEADERS': headers, 'COPTS': options, 'DEFINES': definitions}
    (overlay / 'native/base_sources.bzl').write_text(
        '"""Generated by tools/import_base.py from pinned Linux graph."""\n\n' +
        '\n\n'.join(key + ' = ' + json.dumps(value, indent=4) for key, value in data.items()) + '\n')
    mapped = []
    bridges = [
        ('third_party/icu', ['source/common/unicode', 'source/i18n/unicode'], 'unicode', '@chromium_icu//:icu_file', 'icu'),
        ('third_party/zlib', [''], '', '@zlib//:zlib', 'zlib'),
        ('base/third_party/double_conversion', ['double-conversion'], 'double-conversion', '@double-conversion//:double-conversion', 'double_conversion'),
        ('testing/gtest', ['include/gtest'], 'gtest', '@googletest//:gtest_prod', 'gtest_prod'),
        ('third_party/lss', [''], '', '@linux-syscall-support//:linux-syscall-support', 'lss'),
        ('third_party/ced', ['src'], '', '@compact_enc_det//:ced', 'ced'),
    ]
    for relative, directories, canonical, dependency, name in bridges:
        output = overlay / relative
        output.mkdir(parents=True, exist_ok=True)
        bridge_headers, packages = [], {}
        for directory in directories:
            original = args.source_root / relative / directory
            candidates = [original / file for file in ('zlib.h', 'zconf.h')] if name == 'zlib' else sorted(original.glob('*.h'))
            if name == 'gtest_prod':
                candidates = [original / 'gtest_prod.h']
            if name == 'lss':
                candidates = [original / 'linux_syscall_support.h']
            if name == 'ced':
                candidates = sorted(original.rglob('*.h'))
            for header in candidates:
                suffix = str(header.relative_to(args.source_root / relative))
                target = output / suffix
                target.parent.mkdir(parents=True, exist_ok=True)
                delimiters = ('<', '>') if name in ('zlib', 'lss') else ('"', '"')
                canonical_header = str(header.relative_to(original)) if name == 'ced' else (canonical + '/' if canonical else '') + header.name
                target.write_text('#include ' + delimiters[0] + canonical_header + delimiters[1] + '\n')
                owner = header.parent
                upstream = args.source_root / relative
                while owner != upstream and not any((owner / file).is_file() for file in ('BUILD.bazel', 'BUILD')):
                    owner = owner.parent
                package = str(owner.relative_to(upstream))
                owned = str(header.relative_to(owner))
                if package != '.':
                    packages.setdefault(package, []).append(owned)
                    bridge_headers.append('//' + relative + '/' + package + ':' + owned)
                else:
                    bridge_headers.append(suffix)
        for package, files in packages.items():
            (output / package / 'BUILD.bazel').write_text('exports_files(' + json.dumps(files + ['BUILD.bazel']) + ')\n')
        (output / 'BUILD.bazel').write_text(
            'load("@rules_cc//cc:cc_library.bzl", "cc_library")\n'
            'package(default_visibility = ["//visibility:public"])\n'
            'cc_library(name = ' + json.dumps(name) + ', hdrs = ' + json.dumps(bridge_headers) +
            ', includes = [' + json.dumps('/'.join(['..'] * len(Path(relative).parts))) + '], deps = [' + json.dumps(dependency) + '])\n'
            + ('alias(name = "icuuc", actual = ":icu")\nalias(name = "icui18n", actual = ":icu")\n' if name == 'icu' else '')
            + 'exports_files(["BUILD.bazel"])\n')
        for path in sorted(output.rglob('*')):
            if path.is_file():
                destination = str(path.relative_to(overlay))
                owner = path.parent
                while not (owner / 'BUILD.bazel').is_file():
                    owner = owner.parent
                source = '//bcr/overlay/' + str(owner.relative_to(overlay)) + ':' + str(path.relative_to(owner))
                mapped.append((destination, source))
    module = ROOT / 'MODULE.bazel'
    text = module.read_text()
    lines = [line for line in text.splitlines() if not any(
        line.strip().startswith('"' + relative + '/') for relative, *_ in bridges)]
    index = next(i for i, line in enumerate(lines) if line.startswith('        "native/BUILD.bazel":'))
    mapped.append(('native/base_sources.bzl', '//bcr/overlay/native:base_sources.bzl'))
    mapped.append(('native/base.bzl', '//bcr/overlay/native:base.bzl'))
    lines = [line for line in lines if not line.strip().startswith(('"native/base.bzl":', '"native/base_sources.bzl":'))]
    index = next(i for i, line in enumerate(lines) if line.startswith('        "native/BUILD.bazel":'))
    lines[index:index] = [f'        {json.dumps(dest)}: {json.dumps(source)},' for dest, source in mapped]
    module.write_text(sort_archive_files('\n'.join(lines) + '\n'))
    print(f'Imported {sum(map(len, sources.values()))} C++ sources, {len(headers)} headers')


if __name__ == '__main__':
    main()
