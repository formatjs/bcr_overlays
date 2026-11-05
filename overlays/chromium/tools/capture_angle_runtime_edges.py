#!/usr/bin/env python3
"""Recover ANGLE runtime edges omitted by GN's flattened JSON export."""
import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path


def capture(source_root, gn, graph_path):
    relative = 'third_party/angle/gni/angle.gni'
    source = source_root / relative
    original = source.read_text()
    instrumented = original
    for template in ['angle_shared_library', 'angle_source_set', 'angle_static_library']:
        start = instrumented.index('template("' + template + '")')
        end = instrumented.index('\n}', start)
        scope_end = instrumented.rfind('\n  }', start, end)
        if template == 'angle_shared_library':
            scope_end = instrumented.index('\n  }\n  if (is_ios)', start, end)
        statement = '''
    if (defined(data_deps) && data_deps != []) {
      angle_runtime_labels = []
      foreach(angle_runtime_dep, data_deps) {
        angle_runtime_labels += [ get_label_info(angle_runtime_dep, "label_no_toolchain") ]
      }
      write_file("$target_gen_dir/$target_name.angle_runtime_edges.json",
                 {
                   label = get_label_info(":$target_name", "label_no_toolchain")
                   runtime_deps = angle_runtime_labels
                 },
                 "json")
    }
'''
        instrumented = instrumented[:scope_end] + statement + instrumented[scope_end:]
    group_relative = 'third_party/angle/src/common/vulkan/BUILD.gn'
    group_source = source_root / group_relative
    group_original = group_source.read_text()
    group_instrumented = group_original
    for target in ['angle_libvulkan', 'angle_vulkan_entry_points', 'vulkan_validation_layers', 'lunarg_vulkantools']:
        start = group_instrumented.index('group("' + target + '")')
        line_start = group_instrumented.rfind('\n', 0, start) + 1
        indent = group_instrumented[line_start:start]
        end = group_instrumented.index('\n' + indent + '}', start)
        group_instrumented = group_instrumented[:end] + statement + group_instrumented[end:]
    output = source_root / 'out/bazel-import/gen'
    for path in output.rglob('*.angle_runtime_edges.json'):
        path.unlink()
    try:
        source.write_text(instrumented)
        group_source.write_text(group_instrumented)
        subprocess.run([str(gn), 'desc', 'out/bazel-import',
                        '//third_party/angle:libEGL', '--format=json',
                        '--root-target=//chrome:chrome', '--root-pattern=//chrome:chrome'],
                       cwd=source_root, stdout=subprocess.DEVNULL, check=True)
    finally:
        source.write_text(original)
        group_source.write_text(group_original)
    graph = json.loads(gzip.decompress(graph_path.read_bytes()))
    edges = {}
    for path in sorted(output.rglob('*.angle_runtime_edges.json')):
        record = json.loads(path.read_text())
        label = record['label']
        if label not in graph['targets'] or not label.startswith('//third_party/angle'):
            continue
        deps = sorted(record['runtime_deps'])
        if not set(deps).issubset(graph['targets'][label]['deps']):
            raise ValueError('runtime edges differ from captured graph: ' + label)
        if label in edges and edges[label] != deps:
            raise ValueError('conflicting runtime edges: ' + label)
        edges[label] = deps
    if not edges:
        raise ValueError('no ANGLE runtime edges captured')
    return dict(source=relative, source_sha256=hashlib.sha256(original.encode()).hexdigest(),
                graph_sha256=hashlib.sha256(graph_path.read_bytes()).hexdigest(),
                runtime_deps=dict(sorted(edges.items())),
                additional_sources={group_relative: hashlib.sha256(group_original.encode()).hexdigest()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--gn', type=Path, required=True)
    parser.add_argument('--graph', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(capture(args.source_root, args.gn, args.graph), indent=2) + '\n')


if __name__ == '__main__':
    main()
