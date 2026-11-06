# SPDX-License-Identifier: MIT
"""Run Chromium's pinned MIG compiler without host shell utilities."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    for name in ['user', 'server', 'header', 'sheader', 'arch', 'isysroot']:
        parser.add_argument('-' + name, required=True)
    parser.add_argument('-I', dest='includes', action='append', default=[])
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    clang = os.environ['MIGCC']
    migcom = os.environ['MIGCOM']
    source = '#line 1 ' + json.dumps(str(args.source)) + '\n' + args.source.read_text()
    preprocessed = subprocess.run(
        [clang, '-E', '-x', 'c', '-target', args.arch + '-apple-darwin',
         '-D__MACH30__', '-I', str(args.source.parent), '-isysroot', args.isysroot,
         *['-I' + include for include in args.includes], '-'],
        input=source.encode(), stdout=subprocess.PIPE, check=True)
    subprocess.run([migcom, '-user', args.user, '-server', args.server,
                    '-header', args.header, '-sheader', args.sheader],
                   input=preprocessed.stdout, check=True)


if __name__ == '__main__':
    main()
