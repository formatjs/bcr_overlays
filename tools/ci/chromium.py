#!/usr/bin/env python3
"""Build, package and smoke-test the same Chromium artifact on every target."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import struct
import subprocess
import sys
import tarfile


ROOT = Path(__file__).resolve().parents[2]
CONFIGURATION = json.loads((Path(__file__).with_name('platforms.json')).read_text())
PLATFORMS = {item['id']: item for item in CONFIGURATION['platforms']}


def binary_platform(path):
    with path.open('rb') as binary:
        header = binary.read(64)
        if header[:4] == b'\x7fELF' and header[4:6] == b'\x02\x01':
            machine = struct.unpack_from('<H', header, 18)[0]
            return 'linux', {62: 'amd64', 183: 'arm64'}.get(machine)
        if header[:4] == b'\xcf\xfa\xed\xfe':
            machine = struct.unpack_from('<I', header, 4)[0]
            return 'darwin', {0x1000007: 'amd64', 0x100000C: 'arm64'}.get(machine)
        if header[:2] == b'MZ' and len(header) == 64:
            binary.seek(struct.unpack_from('<I', header, 60)[0])
            coff = binary.read(6)
            if coff[:4] == b'PE\0\0' and len(coff) == 6:
                machine = struct.unpack_from('<H', coff, 4)[0]
                return 'windows', {0x8664: 'amd64', 0xAA64: 'arm64'}.get(machine)
    raise ValueError(f'Unsupported executable format: {path}')


def validate_binary(bundle, target):
    executable = bundle / target['executable']
    actual = binary_platform(executable)
    expected = target['os'], target['arch']
    if actual != expected:
        raise ValueError(f'Wrong artifact architecture: expected {expected}, got {actual}')
    return executable


def checksum(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def package(bundle, destination, target, revision):
    validate_binary(bundle, target)
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected a full source commit SHA')
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / ('chromium-' + target['id'] + '.tar.gz')
    manifest = destination / 'artifact.json'
    manifest.write_text(json.dumps({
        'schema_version': 1,
        'platform': target['id'],
        'version': CONFIGURATION['version'],
        'revision': revision,
        'executable': target['executable'],
    }, indent=2) + '\n')
    with tarfile.open(archive, 'w:gz') as output:
        output.add(manifest, arcname='artifact.json')
        output.add(bundle, arcname='bundle')
    manifest.unlink()
    archive.with_suffix(archive.suffix + '.sha256').write_text(checksum(archive) + '\n')
    return archive


def unpack(artifact, destination, target, revision):
    expected = artifact.with_suffix(artifact.suffix + '.sha256').read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{64}', expected) or checksum(artifact) != expected:
        raise ValueError('Artifact SHA256 mismatch')
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(artifact, 'r:gz') as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not name.parts:
                raise ValueError(f'Invalid artifact path: {member.name}')
            if name.parts[0] not in ['artifact.json', 'bundle']:
                raise ValueError(f'Unexpected artifact entry: {member.name}')
        archive.extractall(destination, filter='data')
    manifest = json.loads((destination / 'artifact.json').read_text())
    expected_manifest = {
        'schema_version': 1, 'platform': target['id'],
        'version': CONFIGURATION['version'], 'revision': revision,
        'executable': target['executable'],
    }
    if manifest != expected_manifest:
        raise ValueError('Artifact provenance does not match this workflow run')
    bundle = destination / 'bundle'
    validate_binary(bundle, target)
    return bundle


def build(target, destination, revision, hosted=False):
    bazel = [os.environ.get('BAZEL', 'bazel')]
    flags = ['--config=browser']
    if hosted:
        if not os.environ.get('BUILDBUDDY_CI_RUNNER_ABSPATH'):
            raise ValueError('Hosted mode requires a BuildBuddy workflow runner')
        flags.append('--config=buildbuddy')
    if target['os'] == 'windows':
        flags.extend([
            '--repo_env=BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA=1',
            '--repo_env=BAZEL_WINDOWS_SDK_EULA=1',
        ])
    label = '//tools/ci:' + target['id']
    subprocess.run([*bazel, 'build', *flags, label], cwd=ROOT, check=True)
    outputs = subprocess.check_output(
        [*bazel, 'cquery', *flags, '--output=files', label], cwd=ROOT, text=True,
    ).splitlines()
    if len(outputs) != 1:
        raise ValueError(f'Expected one browser bundle, got {outputs!r}')
    return package(ROOT / outputs[0], destination, target, revision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['matrix', 'build', 'package', 'smoke'])
    parser.add_argument('--platform', choices=sorted(PLATFORMS))
    parser.add_argument('--revision')
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--artifact', type=Path)
    parser.add_argument('--screenshots', type=Path, help='Rendering evidence directory for smoke tests')
    parser.add_argument('--buildbuddy-hosted', action='store_true',
                        help='Use credentials injected by the BuildBuddy workflow runner')
    args = parser.parse_args()
    if args.command == 'matrix':
        print(json.dumps({'include': CONFIGURATION['platforms']}, separators=(',', ':')))
        return
    if not args.platform or not args.revision or not args.directory:
        parser.error('--platform, --revision and --directory are required')
    target = PLATFORMS[args.platform]
    if args.command == 'build':
        print(build(target, args.directory, args.revision, hosted=args.buildbuddy_hosted))
    elif args.command == 'package':
        if not args.bundle:
            parser.error('--bundle is required')
        print(package(args.bundle, args.directory, target, args.revision))
    else:
        host_os = {'Linux': 'linux', 'Darwin': 'darwin', 'Windows': 'windows'}.get(platform.system())
        host_arch = {'x86_64': 'amd64', 'amd64': 'amd64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(platform.machine().lower())
        if (host_os, host_arch) != (target['os'], target['arch']):
            raise ValueError(f'Smoke runner does not match {target["id"]}')
        if not args.artifact:
            parser.error('--artifact is required')
        bundle = unpack(args.artifact, args.directory, target, args.revision)
        subprocess.run([
            sys.executable, str(ROOT / 'overlays/chromium/tools/check_browser.py'),
            str(bundle), '--executable', target['executable'],
            '--expected-version', CONFIGURATION['version'],
        ], check=True)
        screenshots = args.screenshots or args.directory.parent / 'rendering'
        subprocess.run([
            sys.executable, '-m', 'tools.ci.check_rendering', str(bundle.resolve()),
            '--executable', target['executable'], '--output', str(screenshots.resolve()),
        ], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
