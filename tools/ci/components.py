"""Cross-build component probes on BuildBuddy; unpack them on native runners."""

import argparse
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile

from tools.ci.chromium import PLATFORMS, ROOT, package, unpack


def component_target(identifier):
    target = dict(PLATFORMS[identifier])
    target['id'] = 'components-' + identifier
    target['executable'] = 'rust-' + identifier + ('.exe' if target['os'] == 'windows' else '')
    return target


def build(identifier, destination, revision):
    if not os.environ.get('BUILDBUDDY_CI_RUNNER_ABSPATH'):
        raise ValueError('Component builds require a BuildBuddy workflow runner')
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected a full source commit SHA')
    target = component_target(identifier)
    probes = ['rust', 'expat']
    if target['os'] != 'linux':
        probes += ['allocator', 'base', 'ipc', 'network', 'graphics', 'v8', 'dawn', 'angle', 'gpu']
    if target['os'] == 'windows':
        probes += ['dxc']
    flags = ['--config=buildbuddy', '--//tools/ci:revision=' + revision]
    if target['os'] == 'darwin':
        flags += ['--strategy=CppLink=sandboxed', '--remote_max_connections=8']
    if target['os'] == 'windows':
        flags += ['--repo_env=BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA=1',
                  '--repo_env=BAZEL_WINDOWS_SDK_EULA=1']
    bazel = os.environ.get('BAZEL', 'bazel')
    subprocess.run([bazel, 'build', *flags,
                    *['//tools/ci:' + probe + '-' + identifier for probe in probes]],
                   cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix='chromium-components-') as temporary:
        bundle = Path(temporary) / 'probes'
        subprocess.run([
            sys.executable, '-m', 'tools.ci.collect_allocator_probes',
            '--bazel', bazel, '--platform', identifier, '--output', str(bundle),
            *['--bazel-arg=' + flag for flag in flags],
        ], cwd=ROOT, check=True)
        return package(bundle, destination, target, revision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'unpack'])
    parser.add_argument('--platform', required=True, choices=sorted(PLATFORMS))
    parser.add_argument('--revision', required=True)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--artifact', type=Path)
    args = parser.parse_args()
    if args.command == 'build':
        print(build(args.platform, args.directory, args.revision))
    else:
        target = component_target(args.platform)
        host_os = {'Linux': 'linux', 'Darwin': 'darwin', 'Windows': 'windows'}.get(platform.system())
        host_arch = {'x86_64': 'amd64', 'amd64': 'amd64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(platform.machine().lower())
        if (host_os, host_arch) != (target['os'], target['arch']):
            raise ValueError('Component smoke runner architecture does not match artifact')
        if not args.artifact:
            parser.error('--artifact is required')
        print(unpack(args.artifact, args.directory, target, args.revision))


if __name__ == '__main__':
    main()
