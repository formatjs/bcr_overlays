#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the captured Qt GNU ABI and staged runtime loader paths."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys


LOAD_VERSION = '''
import ctypes
import sys
library = ctypes.CDLL(sys.argv[1])
library.qVersion.restype = ctypes.c_char_p
actual = library.qVersion().decode()
if actual != sys.argv[2]:
    raise SystemExit(f'Qt version mismatch: {actual} != {sys.argv[2]}')
'''


def check_shim(directory, major, expected):
    library = directory / f'libqt{major}_shim.so'
    if not library.is_file():
        raise ValueError(f'missing Qt shim: {library}')
    symbols = subprocess.check_output(['nm', '-C', str(library)], text=True)
    if not symbols.strip():
        raise ValueError(f'Qt {major}: symbol table required to verify GNU ABI')
    if 'std::__1::' in symbols:
        raise ValueError(f'Qt {major}: libc++ ABI leaked into GNU shim')
    dynamic = subprocess.check_output(['readelf', '-d', str(library)], text=True)
    if not re.search(r'\(NEEDED\).*\[libstdc\+\+\.so\.6\]', dynamic):
        raise ValueError(f'Qt {major}: missing GNU C++ runtime dependency')
    paths = re.findall(r'\(RPATH\).*\[([^]]+)\]', dynamic)
    if not paths or '$ORIGIN/lib' not in paths[0].split(':'):
        raise ValueError(f'Qt {major}: missing adjacent lib/ RPATH')
    environment = dict(os.environ)
    environment.pop('LD_LIBRARY_PATH', None)
    result = subprocess.run(
        [sys.executable, '-c', LOAD_VERSION, str(library), expected],
        env=environment, text=True, capture_output=True,
    )
    if result.returncode:
        raise ValueError(f'Qt {major}: runtime load failed: {result.stderr.strip()}')
    print(f'Qt {expected}: GNU ABI and staged runtime load passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Bundle containing Qt shims and adjacent lib/')
    args = parser.parse_args()
    for major, expected in [(5, '5.15.2'), (6, '6.4.2')]:
        check_shim(args.directory.resolve(), major, expected)


if __name__ == '__main__':
    main()
