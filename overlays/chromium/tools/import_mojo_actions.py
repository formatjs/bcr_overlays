#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Translate browser Mojo generator closures to sharded native Bazel actions."""

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = '//out/bazel-import/'
NODE = '//third_party/node/linux/node-linux-x64/bin/node'
CONTROL = [
    '//mojo/public/interfaces/bindings:bindings__generator',
    '//mojo/public/interfaces/bindings:bindings_shared__generator',
    '//mojo/public/interfaces/bindings:bindings__generate_message_ids',
    '//mojo/public/interfaces/bindings:bindings_js__generator',
]


def action_name(label):
    return 'mojo_' + hashlib.sha256(label.encode()).hexdigest()[:16]


def input_paths(target):
    return set(target.get('inputs', []) + target.get('sources', []) + [target['script']])


def replace_block(path, start, end, block):
    text = path.read_text()
    if start in text:
        before, remaining = text.split(start, 1)
        _, after = remaining.split(end, 1)
        text = before + start + '\n' + block + '\n' + end + after
    else:
        text += '\n' + start + '\n' + block + '\n' + end + '\n'
    path.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('source', type=Path)
    parser.add_argument('--scope', choices=['control', 'browser'], default='browser')
    args = parser.parse_args()
    graph = json.loads(gzip.decompress(args.graph.read_bytes()))
    targets = graph['targets']
    selected = CONTROL if args.scope == 'control' else [
        label for label, target in targets.items()
        if target.get('script', '').startswith('//mojo/')
    ]
    closure, reused = set(), {}

    def visit(label):
        if label in closure or label in reused:
            return
        target = targets[label]
        if target.get('script') == '//build/write_buildflag_header.py':
            reused[label] = 'flags_' + hashlib.sha256(label.encode()).hexdigest()[:16]
            return
        if target['type'] not in ('action', 'generated_file', 'group'):
            raise ValueError(f'unsupported Mojo prerequisite: {label} {target["type"]}')
        closure.add(label)
        for dep in target.get('deps', []):
            visit(dep)

    for label in selected:
        visit(label)
    sources = {'ROOT_SOURCES': set(), 'BUILD_SOURCES': set()}

    def native_label(label):
        return ':' + reused.get(label, action_name(label))

    def file_label(path):
        if path == NODE:
            return '@nodejs_linux_amd64//:node_bin'
        if path.startswith(BUILD_DIR):
            return '//native:' + path.removeprefix(BUILD_DIR)
        if not path.startswith('//') or not (args.source / path[2:]).is_file():
            raise ValueError(f'missing source: {path}')
        if path.startswith('//build/'):
            relative = path.removeprefix('//build/')
            sources['BUILD_SOURCES'].add(relative)
            return '//build:' + relative
        relative = path[2:]
        sources['ROOT_SOURCES'].add(relative)
        return '//:' + relative

    def mapping(paths):
        return {file_label(path): path[2:] for path in sorted(paths)}

    all_paths, all_arguments = set(), set()
    for label in closure:
        target = targets[label]
        all_paths.update(target.get('inputs', []) + target.get('sources', []) + target.get('outputs', []))
        if target['type'] == 'action':
            all_paths.add(target['script'])
            all_arguments.update(target.get('args', []) + target.get('response_file_contents', []))
    paths = sorted(all_paths)
    arguments = sorted(all_arguments)
    path_ids = {path: index for index, path in enumerate(paths)}
    argument_ids = {value: index for index, value in enumerate(arguments)}

    def encoded_inputs(values):
        mapping(values)
        return 'input_files(' + json.dumps([path_ids[path] for path in sorted(values)]) + ')'

    def encoded_arguments(values):
        return 'arguments(' + json.dumps([argument_ids[value] for value in values]) + ')'

    by_script = defaultdict(list)
    for label in sorted(closure):
        if targets[label]['type'] == 'action':
            by_script[targets[label]['script']].append(input_paths(targets[label]))
    common = {script: set.intersection(*sets) for script, sets in by_script.items()}
    output = ROOT / 'bcr/overlay/native'
    parameters = ['"""Interned file paths and arguments for generated Mojo rules."""', '',
                  '_PATHS = ' + json.dumps(paths, indent=4), '',
                  '_ARGUMENTS = ' + json.dumps(arguments, indent=4), '',
                  'def source_path(index):',
                  '    """Return Chromium-relative path for an interned file index."""',
                  '    return _PATHS[index][2:]', '',
                  'def _label(path):',
                  '    if path.startswith("//out/bazel-import/"):',
                  '        return "//native:" + path[len("//out/bazel-import/"):]',
                  '    if path == ' + json.dumps(NODE) + ':',
                  '        return "@nodejs_linux_amd64//:node_bin"',
                  '    if path.startswith("//build/"):',
                  '        return "//build:" + path[len("//build/"):]',
                  '    return "//:" + path[2:]', '',
                  'def input_files(indices):',
                  '    """Resolve interned input indices to labels and logical paths."""',
                  '    return {_label(_PATHS[i]): source_path(i) for i in indices}', '',
                  'def output_files(indices):',
                  '    """Resolve interned output indices to logical build paths."""',
                  '    return {_PATHS[i][len("//out/bazel-import/"):]: _PATHS[i][len("//out/bazel-import/"):] for i in indices}', '',
                  'def arguments(indices):',
                  '    """Resolve ordered generator arguments."""',
                  '    return [_ARGUMENTS[i] for i in indices]', '']
    (output / 'mojo_parameters.bzl').write_text('\n'.join(parameters))
    shared = ['"""Shared declared source inputs for native Mojo actions."""', '',
              'load(":python_action.bzl", "chromium_filegroup")', '',
              'load(":mojo_parameters.bzl", "input_files")', '',
              '# buildifier: disable=unnamed-macro',
              'def declare_common_inputs():',
              '    """Declare fixed source groups from captured browser graph."""']
    for script, paths in sorted(common.items()):
        shared.extend([
            '    chromium_filegroup(',
            '        name = ' + json.dumps('inputs_' + action_name(script)) + ',',
            '        srcs = ' + encoded_inputs(paths) + ',',
            '    )',
        ])
    (output / 'mojo_common_inputs.bzl').write_text('\n'.join(shared) + '\n')
    chunks = []
    labels = sorted(closure)
    for index in range(0, len(labels), 160):
        chunk = f'mojo_actions_{index // 160:03d}.bzl'
        chunks.append(chunk)
        lines = [
            '"""Generated Mojo action shard; run tools/import_mojo_actions.py."""', '',
            'load(":python_action.bzl", "chromium_filegroup", "chromium_python_action")', '',
            'load(":mojo_parameters.bzl", "arguments", "input_files", "output_files", "source_path")', '',
            '# buildifier: disable=unnamed-macro',
            'def declare_actions():',
            '    """Declare fixed targets from captured browser graph."""',
        ]
        for label in labels[index:index + 160]:
            target = targets[label]
            dependencies = [native_label(dep) for dep in target.get('deps', [])]
            if target['type'] in ('group', 'generated_file'):
                paths = target.get('outputs', []) if target['type'] == 'generated_file' else target.get('inputs', [])
                lines.extend([
                    '    chromium_filegroup(',
                    '        name = ' + json.dumps(action_name(label)) + ',',
                    '        srcs = ' + encoded_inputs(set(paths)) + ',',
                    '        deps = ' + json.dumps(dependencies) + ',',
                    '    )',
                ])
                continue
            script = target['script']
            paths = input_paths(target) - common[script]
            outputs = {path.removeprefix(BUILD_DIR): path.removeprefix(BUILD_DIR)
                       for path in target['outputs']}
            if any(path.startswith('//') for path in outputs):
                raise ValueError(f'output outside captured build directory: {label}')
            if script.endswith('/minify_with_terser.py'):
                dependencies.append(':node_npm_sources')
            lines.extend([
                '    chromium_python_action(',
                '        name = ' + json.dumps(action_name(label)) + ',',
                '        srcs = ' + encoded_inputs(paths) + ',',
                '        outs = output_files(' + json.dumps([path_ids[path] for path in target['outputs']]) + '),',
                '        script = source_path(' + str(path_ids[script]) + '),',
                '        args = ' + encoded_arguments(target.get('args', [])) + ',',
                '        response_file_contents = ' + encoded_arguments(target.get('response_file_contents', [])) + ',',
                '        deps = ' + json.dumps(dependencies + [':inputs_' + action_name(script)]) + ',',
                *(['        exec_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],']
                  if NODE in input_paths(target) else []),
                '    )',
            ])
        (output / chunk).write_text('\n'.join(lines) + '\n')
    for path in output.glob('mojo_actions_*.bzl'):
        if path.name not in chunks:
            path.unlink()
    main = ['"""Native browser Mojo generators; regenerate with tools/import_mojo_actions.py."""', '',
            'load(":python_action.bzl", "chromium_filegroup")',
            'load(":mojo_common_inputs.bzl", "declare_common_inputs")']
    main.extend(f'load(":{chunk}", _declare_{i} = "declare_actions")' for i, chunk in enumerate(chunks))
    main.extend(['', 'def native_mojo_bindings(name):',
                 '    """Declare browser Mojo generator closures.', '',
                 '    Args:', '        name: Target collecting browser Mojo generated bindings.',
                 '    """', '    declare_common_inputs()'])
    main.extend(f'    _declare_{i}()' for i in range(len(chunks)))
    main.extend(['    chromium_filegroup(', '        name = name,',
                 '        deps = ' + json.dumps([native_label(label) for label in sorted(selected)]) + ',',
                 '    )', '    chromium_filegroup(', '        name = "mojo_control_bindings",',
                 '        deps = ' + json.dumps([native_label(label) for label in CONTROL]) + ',', '    )'])
    (output / 'mojo_actions.bzl').write_text('\n'.join(main) + '\n')
    (output / 'mojo_source_files.bzl').write_text(
        '"""Declared inputs for native browser Mojo generation."""\n\n' +
        '\n\n'.join(name + ' = ' + json.dumps(sorted(paths), indent=4)
                    for name, paths in sources.items()) + '\n')
    (ROOT / 'native/mojo_targets.json').write_text(json.dumps(
        {label: '//native:' + reused.get(label, action_name(label))
         for label in sorted(closure | reused.keys())}, indent=4) + '\n')
    for path, values in [(ROOT / 'bcr/overlay/BUILD.bazel', sources['ROOT_SOURCES']),
                         (ROOT / 'bcr/overlay/build/BUILD.bazel', sources['BUILD_SOURCES'])]:
        replace_block(path, '# BEGIN GENERATED MOJO INPUTS', '# END GENERATED MOJO INPUTS',
                      'exports_files(' + json.dumps(sorted(values), indent=4) + ')')
    module = ROOT / 'MODULE.bazel'
    text = module.read_text()
    text = '\n'.join(line for line in text.splitlines() if '"native/mojo_' not in line) + '\n'
    module.write_text(text)
    files = ['mojo_actions.bzl', 'mojo_common_inputs.bzl', 'mojo_parameters.bzl', 'mojo_source_files.bzl'] + chunks
    marker = '        "native/BUILD.bazel": "//bcr/overlay/native:BUILD.bazel",'
    text = module.read_text()
    entries = '\n'.join(f'        "native/{name}": "//bcr/overlay/native:{name}",' for name in files)
    if marker not in text:
        raise ValueError('development MODULE.bazel missing native overlay entry')
    module.write_text(text.replace(marker, marker + '\n' + entries))
    print(f'Imported {len(closure)} targets, reused {len(reused)}, '
          f'{sum(map(len, sources.values()))} source inputs, {len(chunks)} shards')


if __name__ == '__main__':
    main()
