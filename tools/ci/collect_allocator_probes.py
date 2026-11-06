"""Collect architecture-checked cross-compiled executables for native CI smoke."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.ci.chromium import ROOT, binary_platform


def collect_v8(files, platform, destination):
    """Keep V8 startup data beside its architecture-checked executable."""
    runtime_names = {'icudtl.dat', 'snapshot_blob.bin'}
    runtime = {file.name: file for file in files if file.name in runtime_names}
    executables = [file for file in files if file.name not in runtime_names]
    operating_system, arch = platform.split('-')
    if (len(files) != 3 or set(runtime) != runtime_names or len(executables) != 1
            or binary_platform(executables[0]) != (operating_system, arch)):
        raise ValueError('V8 requires one matching executable, ICU data and snapshot')
    destination.mkdir(parents=True, exist_ok=True)
    suffix = '.exe' if operating_system == 'windows' else ''
    shutil.copy2(executables[0], destination / ('v8-' + platform + suffix))
    for name, source in runtime.items():
        shutil.copy2(source, destination / name)


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
    targets = [
        ('allocator-windows-amd64', 'windows-amd64'),
        ('allocator-windows-arm64', 'windows-arm64'),
        ('allocator-darwin-arm64', 'darwin-arm64'),
        ('base-windows-amd64', 'windows-amd64'),
        ('base-windows-arm64', 'windows-arm64'),
        ('base-darwin-arm64', 'darwin-arm64'),
        ('ipc-darwin-arm64', 'darwin-arm64'),
        ('ipc-windows-amd64', 'windows-amd64'),
        ('ipc-windows-arm64', 'windows-arm64'),
        ('network-darwin-arm64', 'darwin-arm64'),
        ('network-windows-amd64', 'windows-amd64'),
        ('network-windows-arm64', 'windows-arm64'),
        ('graphics-darwin-arm64', 'darwin-arm64'),
        ('graphics-windows-amd64', 'windows-amd64'),
        ('graphics-windows-arm64', 'windows-arm64'),
    ]
    v8_platforms = ['darwin-arm64', 'windows-amd64', 'windows-arm64']
    names = [target for target, _ in targets] + ['v8-' + platform for platform in v8_platforms]
    expression = 'set(' + ' '.join('//tools/ci:' + name for name in names) + ')'
    command = startup + ['cquery', expression,
                        '--repo_env=BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA=1',
                        '--repo_env=BAZEL_WINDOWS_SDK_EULA=1', '--output=starlark',
                        '--starlark:expr=json.encode({"label": str(target.label), "files": [f.path for f in target.files.to_list()]})']
    artifacts = {}
    for line in subprocess.check_output(command, cwd=ROOT, text=True).splitlines():
        result = json.loads(line)
        name = result['label'].split(':')[-1].removesuffix('_with_cfg')
        if name not in names or name in artifacts:
            raise ValueError('Unexpected or duplicate probe: ' + result['label'])
        artifacts[name] = [execution_root / file for file in result['files']]
    if set(artifacts) != set(names):
        raise ValueError('Missing probe artifacts: ' + ', '.join(sorted(set(names) - set(artifacts))))
    args.output.mkdir(parents=True, exist_ok=True)
    for target, platform in targets:
        operating_system, arch = platform.split('-')
        label = '//tools/ci:' + target
        executables = artifacts[target]
        if len(executables) != 1 or binary_platform(executables[0]) != (operating_system, arch):
            raise ValueError(f'{label}: expected one {operating_system} {arch} executable')
        suffix = '.exe' if operating_system == 'windows' else ''
        shutil.copy2(executables[0], args.output / (target + suffix))
    for platform in v8_platforms:
        collect_v8(artifacts['v8-' + platform], platform, args.output / ('v8-' + platform))


if __name__ == '__main__':
    main()
