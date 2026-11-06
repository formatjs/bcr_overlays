#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Copy declared runtime files into a relocatable bundle."""

import argparse
import json
from pathlib import Path, PurePosixPath
import posixpath
import shutil


def assemble(manifest):
    files = {}
    for actual, logical in manifest['inputs']:
        relative = PurePosixPath(logical)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts:
            raise ValueError(f'invalid runtime path: {logical}')
        normalized = str(relative)
        if normalized in files:
            raise ValueError(f'duplicate runtime path: {normalized}')
        source = Path(actual)
        if not source.is_file() and not source.is_dir():
            raise FileNotFoundError(f'missing runtime input: {source}')
        files[normalized] = source
    for child in files:
        for parent in PurePosixPath(child).parents:
            if str(parent) in files:
                raise ValueError(f'overlapping runtime paths: {parent}, {child}')
    output = Path(manifest['output'])
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f'runtime output must be empty: {output}')
    for logical, source in sorted(files.items()):
        destination = output / logical
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination)
    for logical, target in sorted(manifest.get('symlinks', {}).items()):
        relative = PurePosixPath(logical)
        resolved = posixpath.normpath(str(relative.parent / target))
        if (relative.is_absolute() or '..' in relative.parts or not relative.parts
                or PurePosixPath(target).is_absolute() or resolved == '..'
                or resolved.startswith('../')):
            raise ValueError(f'invalid runtime symlink: {logical}: {target}')
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    assemble(json.loads(args.manifest.read_text()))


if __name__ == '__main__':
    main()
