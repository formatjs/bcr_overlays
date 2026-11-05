#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture GN maintainer metadata for native Bazel translation, never execution."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import posixpath

POOL_FIELDS = frozenset((
    'all_dependent_configs', 'arflags', 'asmflags', 'cflags', 'cflags_c',
    'cflags_cc', 'cflags_objc', 'cflags_objcc', 'configs', 'defines',
    'include_dirs', 'ldflags', 'libs', 'rustflags', 'swiftflags',
))


def target_closure(project, roots):
    """Retain data and host-tool dependencies omitted by GN IDE filters."""
    targets = project['targets']
    selected = {}
    pending = list(roots)
    while pending:
        label = pending.pop()
        if label in selected:
            continue
        if label not in targets:
            raise ValueError(f'missing dependency in complete GN graph: {label}')
        selected[label] = targets[label]
        pending.extend(targets[label].get('deps', []))
    return {**project, 'targets': selected}


def capture(project, runtime, source_root, replacements, runtime_inputs=None):
    """Reject incomplete graphs; preserve target semantics and generated contents."""
    def portable(value):
        if isinstance(value, str):
            for old, new in replacements:
                value = value.replace(old, new)
            if '/tmp/' in value or '/home/' in value:
                raise ValueError(f'unmapped host path: {value}')
            return value
        if isinstance(value, list):
            return [portable(v) for v in value]
        if isinstance(value, dict):
            return {k: portable(v) for k, v in value.items()}
        return value

    targets = project['targets']
    producers = {}
    for label, target in targets.items():
        for dep in target.get('deps', []):
            if dep not in targets:
                raise ValueError(f'{label}: missing dependency {dep}')
        for output in target.get('outputs', []):
            if not output.startswith('//') or posixpath.normpath(output) != output:
                raise ValueError(f'invalid output path: {output}')
            if output in producers:
                raise ValueError(f'duplicate output {output}: {producers[output]}, {label}')
            producers[output] = label

    build_dir = project['build_settings']['build_dir'].rstrip('/')
    runtime_inputs = runtime_inputs or {}
    runtime_paths = {posixpath.normpath(build_dir + '/' + path)
                     for value in runtime.values() for path in value['runtime_deps']}
    captured_runtime = {}
    for output, source in sorted(runtime_inputs.items()):
        if output not in runtime_paths:
            raise ValueError(f'unused runtime input: {output}')
        if not output.startswith(build_dir + '/') or posixpath.normpath(output) != output:
            raise ValueError(f'invalid runtime input output: {output}')
        if output in producers:
            raise ValueError(f'runtime input already has a producer: {output}')
        if (not source.startswith('//') or source.startswith('///')
                or posixpath.normpath(source) != source
                or source.startswith(build_dir + '/')):
            raise ValueError(f'invalid runtime input source: {source}')
        captured_runtime[output] = {
            'source': source,
            'sha256': hashlib.sha256((source_root / source[2:]).read_bytes()).hexdigest(),
        }
    runtime_files = {}
    for label, value in runtime.items():
        if label not in targets:
            raise ValueError(f'unknown runtime target: {label}')
        files = sorted({posixpath.normpath(build_dir + '/' + p)
                        for p in value['runtime_deps']})
        for name in files:
            if (name.startswith(build_dir + '/') and name not in producers
                    and name not in captured_runtime):
                raise ValueError(f'{label}: missing runtime producer {name}')
            if not name.startswith('//') or name.startswith('///'):
                raise ValueError(f'invalid runtime path {name}')
        runtime_files[label] = files

    pool = []
    indices = {}
    captured = {}
    generated = {}
    for label, target in sorted(targets.items()):
        record = {}
        for key, value in sorted(target.items()):
            value = portable(value)
            if key in POOL_FIELDS:
                signature = json.dumps(value, separators=(',', ':'), sort_keys=True)
                if signature not in indices:
                    indices[signature] = len(pool)
                    pool.append(value)
                record[key] = {'pool': indices[signature]}
            else:
                record[key] = value
        captured[label] = record
        if target['type'] == 'generated_file':
            for output in target['outputs']:
                if not output.startswith(build_dir + '/'):
                    raise ValueError(f'generated file outside build directory: {output}')
                path = source_root / output[2:]
                generated[output] = portable(path.read_text())

    for target in targets.values():
        inputs = target.get('inputs', []) + target.get('sources', [])
        arguments = target.get('args', [])
        if '--expected-outputs-file' in arguments:
            index = arguments.index('--expected-outputs-file')
            inputs.append(posixpath.normpath(build_dir + '/' + arguments[index + 1]))
        for name in inputs:
            if (not name.startswith(build_dir + '/') or name in producers
                    or name in captured_runtime):
                continue
            if posixpath.normpath(name) != name:
                raise ValueError(f'invalid generated input path: {name}')
            path = source_root / name[2:]
            if not path.is_file():
                raise ValueError(f'unproduced generated input unavailable: {name}')
            generated[name] = portable(path.read_text())

    settings = {k: v for k, v in project['build_settings'].items()
                if k != 'root_path'}
    result = {
        'schema_version': 1,
        'build_settings': portable(settings),
        'pool': pool,
        'targets': captured,
        'runtime_files': runtime_files,
        'generated_files': generated,
    }
    if captured_runtime:
        result['runtime_inputs'] = captured_runtime
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--runtime-deps', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--llvm-root', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--gn-version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', action='append', help='Capture this complete dependency closure')
    parser.add_argument('--runtime-input', action='append', default=[], metavar='OUTPUT=SOURCE',
                        help='Declare a source runtime file normally copied by an SDK setup hook')
    args = parser.parse_args()
    project = json.loads(args.project.read_text())
    if args.target:
        project = target_closure(project, args.target)
    runtime_inputs = {}
    for value in args.runtime_input:
        output, separator, source = value.partition('=')
        if not separator or output in runtime_inputs:
            parser.error('runtime inputs must be unique OUTPUT=SOURCE pairs')
        runtime_inputs[output] = source
    graph = capture(project,
                    json.loads(args.runtime_deps.read_text()), args.source_root,
                    [(str(args.llvm_root), '$LLVM_ROOT'),
                     (str(args.source_root), '$SOURCE_ROOT')], runtime_inputs=runtime_inputs)
    args_file = args.source_root / graph['build_settings']['build_dir'][2:] / 'args.gn'
    configuration = (args_file.read_text()
                     .replace(str(args.llvm_root), '$LLVM_ROOT')
                     .replace(str(args.source_root), '$SOURCE_ROOT'))
    graph['provenance'] = {
        'chromium_revision': args.revision,
        'gn_version': args.gn_version,
        'args_gn': configuration,
        'deps_sha256': hashlib.sha256((args.source_root / 'DEPS').read_bytes()).hexdigest(),
    }
    payload = json.dumps(graph, sort_keys=True, separators=(',', ':')).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress(payload, mtime=0))
    summary = {
        'schema_version': 1,
        'provenance': graph['provenance'],
        'graph_sha256': hashlib.sha256(payload).hexdigest(),
        'compressed_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
        'target_types': dict(sorted(Counter(t['type'] for t in graph['targets'].values()).items())),
        'runtime_file_count': {k: len(v) for k, v in graph['runtime_files'].items()},
        'generated_file_count': len(graph['generated_files']),
        'pool_entries': len(graph['pool']),
    }
    args.output.with_suffix('.summary.json').write_text(json.dumps(summary, indent=4) + '\n')
    print(f"Captured {len(graph['targets'])} targets, {len(payload)} bytes, "
          f"{args.output.stat().st_size} compressed bytes")


if __name__ == '__main__':
    main()
