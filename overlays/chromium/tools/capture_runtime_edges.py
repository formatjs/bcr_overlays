#!/usr/bin/env python3
"""Recover runtime dependencies from a top-level GN target declaration."""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path


def capture(source_root, gn, graph_path, label):
    if not re.fullmatch(r'//[A-Za-z0-9_./-]+:[A-Za-z0-9_.+-]+', label):
        raise ValueError('expected an absolute GN target label')
    directory, name = label[2:].split(':')
    if '..' in Path(directory).parts:
        raise ValueError('target directory escapes source root')
    relative = directory + '/BUILD.gn'
    source = source_root / relative
    original_bytes = source.read_bytes()
    original = original_bytes.decode()
    opening = re.search(r'^(?:component|source_set|static_library|shared_library|group)\("' +
                        re.escape(name) + r'"\) \{', original, re.MULTILINE)
    if not opening:
        raise ValueError('top-level GN target declaration not found: ' + label)
    end = original.index('\n}', opening.end())
    filename = 'runtime_edges_' + hashlib.sha256(label.encode()).hexdigest()[:16] + '.json'
    statement = '''
  captured_runtime_labels = []
  if (defined(data_deps)) {
    foreach(captured_runtime_dep, data_deps) {
      captured_runtime_labels += [ get_label_info(captured_runtime_dep, "label_no_toolchain") ]
    }
  }
  write_file("$root_build_dir/''' + filename + '''", captured_runtime_labels, "json")
'''
    output = source_root / 'out/bazel-import' / filename
    output.unlink(missing_ok=True)
    try:
        source.write_text(original[:end] + statement + original[end:])
        subprocess.run([str(gn), 'desc', 'out/bazel-import', label, '--format=json',
                        '--root-target=//chrome:chrome', '--root-pattern=//chrome:chrome'],
                       cwd=source_root, stdout=subprocess.DEVNULL, check=True)
    finally:
        source.write_bytes(original_bytes)
    graph = json.loads(gzip.decompress(graph_path.read_bytes()))
    deps = sorted(set(json.loads(output.read_text())))
    if not set(deps).issubset(graph['targets'][label]['deps']):
        raise ValueError('runtime edges differ from captured graph: ' + label)
    return dict(source=relative, source_sha256=hashlib.sha256(original_bytes).hexdigest(),
                graph_sha256=hashlib.sha256(graph_path.read_bytes()).hexdigest(),
                runtime_deps={label: deps})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--gn', type=Path, required=True)
    parser.add_argument('--graph', type=Path, required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.source_root, args.gn, args.graph, args.target)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
