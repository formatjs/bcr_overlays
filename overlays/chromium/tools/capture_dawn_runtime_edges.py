#!/usr/bin/env python3
"""Recover Dawn runtime edges omitted by GN's flattened JSON export."""
import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path


def capture(source_root, gn, graph_path):
    relative = 'third_party/dawn/src/dawn/native/BUILD.gn'
    source = source_root / relative
    original = source.read_text()
    instrumented = original
    scopes = {'sources': 'source_set("sources")', 'static': 'dawn_component("native")'}
    for name, opening in scopes.items():
        start = instrumented.index(opening)
        end = instrumented.index('\n}', start)
        statement = ('\n  captured_runtime_labels = []\n'
                     '  foreach(captured_runtime_dep, data_deps) {\n'
                     '    captured_runtime_labels += [ get_label_info(captured_runtime_dep, "label_no_toolchain") ]\n'
                     '  }\n'
                     '  write_file("$root_build_dir/dawn_' + name + '_data_deps.json", '
                     'captured_runtime_labels, "json")\n')
        instrumented = instrumented[:end] + statement + instrumented[end:]
    try:
        source.write_text(instrumented)
        subprocess.run([str(gn), 'desc', 'out/bazel-import',
                        '//third_party/dawn/src/dawn/native:sources', '--format=json',
                        '--root-target=//chrome:chrome', '--root-pattern=//chrome:chrome'],
                       cwd=source_root, stdout=subprocess.DEVNULL, check=True)
    finally:
        source.write_text(original)
    graph = json.loads(gzip.decompress(graph_path.read_bytes()))
    edges = {}
    for name in scopes:
        label = '//third_party/dawn/src/dawn/native:' + name
        deps = json.loads((source_root / ('out/bazel-import/dawn_' + name + '_data_deps.json')).read_text())
        if not set(deps).issubset(graph['targets'][label]['deps']):
            raise ValueError('runtime edges differ from captured graph: ' + label)
        edges[label] = sorted(deps)
    return dict(source=relative, source_sha256=hashlib.sha256(original.encode()).hexdigest(),
                graph_sha256=hashlib.sha256(graph_path.read_bytes()).hexdigest(), runtime_deps=edges)


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
