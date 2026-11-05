#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Resolve NSS Linux build metadata; never builds binaries or invokes Ninja."""
import argparse
from pathlib import Path
import subprocess
import sys

PARAMETERS = {
    'OS': 'linux', 'target_arch': 'x64', 'host_arch': 'x64', 'python': 'python3',
    'cc_is_clang': '1', 'cc_is_gcc': '0',
    'nspr_include_dir': '/native/nspr/include', 'nspr_lib_dir': '/native/nspr/lib',
    'nss_dist_dir': '/native/nss', 'nss_dist_obj_dir': '/native/nss/obj',
    'disable_tests': '1', 'disable_fips': '0', 'disable_dbm': '0',
    'disable_libpkix': '0', 'use_system_sqlite': '1', 'mozilla_client': '1',
    'enable_sslkeylogfile': '1',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_root', type=Path)
    parser.add_argument('--gyp', type=Path, required=True,
                        help='gyp-next 0.20.5 entry-point script')
    parser.add_argument('--target-arch', choices=('x64', 'arm64'), default='x64')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    parameters = dict(PARAMETERS, target_arch=args.target_arch)
    subprocess.run([sys.executable, str(args.gyp.resolve()), '-f', 'gypd', '--depth=.',
                    *[f'-D{key}={value}' for key, value in parameters.items()],
                    'nss.gyp'], cwd=args.source_root, check=True)
    subprocess.run([sys.executable, str(Path(__file__).with_name('import_sources.py')),
                    str(args.source_root.resolve()),
                    *(['--output', str(args.output.resolve())] if args.output else [])], check=True)


if __name__ == '__main__':
    main()
