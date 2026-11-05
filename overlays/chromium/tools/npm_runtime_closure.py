#!/usr/bin/env python3
"""List installed npm runtime dependencies using Node's nearest-package lookup."""

import argparse
import json
from pathlib import Path


def runtime_closure(root, packages):
    root = root.resolve()
    pending = [root / package for package in packages]
    result = set()
    while pending:
        directory = pending.pop().resolve()
        if directory in result:
            continue
        directory.relative_to(root)
        metadata = json.loads((directory / 'package.json').read_text())
        result.add(directory)
        optional = metadata.get('optionalDependencies', {})
        for name in sorted(set(metadata.get('dependencies', {})) | set(optional)):
            parent = directory
            while parent != root.parent:
                candidate = parent / 'node_modules' / name
                if (candidate / 'package.json').is_file():
                    pending.append(candidate)
                    break
                if parent == root:
                    candidate = root / name
                    if (candidate / 'package.json').is_file():
                        pending.append(candidate)
                        break
                parent = parent.parent
            else:
                if name not in optional:
                    raise ValueError(f'Missing runtime dependency {name} of {directory}')
    return sorted(path.relative_to(root).as_posix() for path in result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('node_modules', type=Path)
    parser.add_argument('packages', nargs='+')
    arguments = parser.parse_args()
    print(json.dumps(runtime_closure(arguments.node_modules, arguments.packages), indent=4))
