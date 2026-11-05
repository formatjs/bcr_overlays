"""Collect architecture-checked Windows executables for native CI smoke."""

import argparse
from pathlib import Path
import shutil
import subprocess

from tools.ci.chromium import ROOT, binary_platform


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--bazel', default='bazel')
    parser.add_argument('--output-user-root')
    args = parser.parse_args()
    startup = [args.bazel, '--batch']
    if args.output_user_root:
        startup.append('--output_user_root=' + args.output_user_root)
    execution_root = Path(subprocess.check_output(
        startup + ['info', 'execution_root'], cwd=ROOT, text=True).strip())
    command = startup + ['cquery', '--repo_env=BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA=1',
                '--repo_env=BAZEL_WINDOWS_SDK_EULA=1', '--output=files']
    args.output.mkdir(parents=True, exist_ok=True)
    for arch in ['amd64', 'arm64']:
        label = '//tools/ci:allocator-windows-' + arch
        files = subprocess.check_output(command + [label], cwd=ROOT, text=True).splitlines()
        executables = [execution_root / name for name in files if name.endswith('.exe')]
        if len(executables) != 1 or binary_platform(executables[0]) != ('windows', arch):
            raise ValueError(f'{label}: expected one Windows {arch} executable')
        shutil.copy2(executables[0], args.output / ('allocator-windows-' + arch + '.exe'))


if __name__ == '__main__':
    main()
