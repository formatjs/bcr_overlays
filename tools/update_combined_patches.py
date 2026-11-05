#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Expose overlay-only targets in shared BCR module overrides."""
from pathlib import Path
import difflib

ROOT = Path(__file__).resolve().parents[1]


def main():
    for module in ['abseil-cpp', 'boringssl']:
        overlay = ROOT / 'overlays' / module / 'bcr/overlay'
        chunks = []
        for path in sorted(overlay.rglob('*')):
            if not path.is_file() or path.name == 'MODULE.bazel':
                continue
            relative = path.relative_to(overlay).as_posix()
            chunks.append(f'diff --git a/{relative} b/{relative}\nnew file mode 100644\n')
            chunks.extend(difflib.unified_diff([], path.read_text().splitlines(True),
                                             fromfile='/dev/null', tofile='b/' + relative))
        name = 'abseil' if module == 'abseil-cpp' else module
        (ROOT / 'build' / (name + '-overlay.patch')).write_text(''.join(chunks))


if __name__ == '__main__':
    main()
