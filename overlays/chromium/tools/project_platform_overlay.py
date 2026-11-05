#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Project imported metadata as a delta over the shared Chromium overlay."""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_overlay', type=Path)
    parser.add_argument('--variant', required=True, choices=['linux_arm64'])
    args = parser.parse_args()
    base = ROOT / 'bcr/overlay'
    output = ROOT / 'platforms' / args.variant / 'overlay'
    source = args.source_overlay.resolve()
    if source in (base.resolve(), output.resolve()):
        parser.error('use a separate imported overlay as the source')
    preserved = {
        'native/base.bzl',
        'native/fonts.bzl',
        'native/blink_rust.bzl',
        'native/platform_runtime.bzl',
        'native/rust/BUILD.bazel',
        'base/allocator/partition_allocator/src/partition_alloc/BUILD.bazel',
    }
    changed = removed = 0
    for path in sorted(source.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if relative.as_posix() in preserved:
            continue
        data = path.read_bytes()
        if path.suffix in ('.bzl', '.bazel', '.json'):
            data = data.replace(b'@chromium_platform_headers//',
                                b'@chromium_platform_headers_cross//')
        target = output / relative
        original = base / relative
        if original.is_file() and original.read_bytes() == data:
            if target.is_file():
                target.unlink()
                removed += 1
            continue
        if target.is_file() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        changed += 1
    print(f'{changed} overrides updated, {removed} redundant overrides removed')


if __name__ == '__main__':
    main()
