#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Copy declared runtime files into a relocatable bundle."""

import argparse
import json
from pathlib import Path, PurePosixPath
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
        if not source.is_file():
            raise FileNotFoundError(f'missing runtime input: {source}')
        files[normalized] = source
    output = Path(manifest['output'])
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f'runtime output must be empty: {output}')
    for logical, source in sorted(files.items()):
        destination = output / logical
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    assemble(json.loads(args.manifest.read_text()))


if __name__ == '__main__':
    main()
