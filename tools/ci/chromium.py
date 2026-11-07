#!/usr/bin/env python3
"""Build, package and smoke-test the same Chromium artifact on every target."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import unquote, urlparse


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


def package_payload(bundle, payload, target):
    validate_binary(bundle, target)
    payload.parent.mkdir(parents=True, exist_ok=True)

    def normalize(member):
        if member.islnk():
            source = bundle / PurePosixPath(member.name).relative_to('bundle')
            member.type = tarfile.REGTYPE
            member.linkname = ''
            member.size = source.stat().st_size
        member.uid = member.gid = member.mtime = 0
        member.uname = member.gname = ''
        member.pax_headers = {}
        member.mode = 0o755 if member.isdir() or member.mode & 0o111 else 0o644
        return member

    with payload.open('wb') as raw, gzip.GzipFile(
            filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=6) as compressed:
        with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT,
                          dereference=False) as output:
            output.add(bundle, arcname='bundle', filter=normalize)
    return payload


def stamp_payload(payload, destination, target, revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected a full source commit SHA')
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / ('chromium-' + target['id'] + '.tar.gz')
    manifest = (json.dumps({
        'schema_version': 1,
        'platform': target['id'],
        'version': CONFIGURATION['version'],
        'revision': revision,
        'executable': target['executable'],
    }, indent=2) + '\n').encode()
    member = tarfile.TarInfo('artifact.json')
    member.size = len(manifest)
    member.mode = 0o644
    # No tar end marker here: the cached payload completes this tar stream.
    prefix = member.tobuf(format=tarfile.PAX_FORMAT) + manifest
    prefix += b'\0' * (-len(manifest) % tarfile.BLOCKSIZE)
    with archive.open('wb') as output:
        with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0, compresslevel=6) as compressed:
            compressed.write(prefix)
        with payload.open('rb') as source:
            shutil.copyfileobj(source, output, length=1024 * 1024)
    archive.with_suffix(archive.suffix + '.sha256').write_text(checksum(archive) + '\n')
    return archive


def package(bundle, destination, target, revision):
    with tempfile.TemporaryDirectory(prefix='chromium-payload-') as temporary:
        payload = package_payload(bundle, Path(temporary) / 'bundle.tar.gz', target)
        return stamp_payload(payload, destination, target, revision)


def grant_windows_sandbox_access(bundle):
    # Match chrome/installer/setup/configure_app_container_sandbox.cc.
    capabilities = (
        'S-1-15-3-1024-3424233489-972189580-2057154623-747635277-1604371224-'
        '316187997-3786583170-1043257646',
        'S-1-15-3-1024-2302894289-466761758-1166120688-1039016420-2430351297-'
        '4240214049-4028510897-3317428798',
    )
    for sid in capabilities:
        subprocess.run(['icacls', str(bundle), '/grant', f'*{sid}:(OI)(CI)(RX)', '/Q'], check=True)


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
    if target['os'] == 'windows' and platform.system() == 'Windows':
        grant_windows_sandbox_access(bundle)
    return bundle


def build(target, destination, revision, hosted=False):
    bazel = [os.environ.get('BAZEL', 'bazel')]
    flags = ['--config=browser']
    if hosted:
        if not os.environ.get('BUILDBUDDY_CI_RUNNER_ABSPATH'):
            raise ValueError('Hosted mode requires a BuildBuddy workflow runner')
        flags.extend(['--config=buildbuddy', '--keep_going'])
        if target['os'] == 'darwin':
            # Bound input downloads for the large framework link.
            flags.extend(['--strategy=CppLink=sandboxed', '--remote_max_connections=8'])
    if target['os'] == 'windows':
        flags.extend([
            '--repo_env=BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA=1',
            '--repo_env=BAZEL_WINDOWS_SDK_EULA=1',
        ])
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected a full source commit SHA')
    label = '//tools/ci:' + target['id'] + '_archive'
    with tempfile.TemporaryDirectory(prefix='chromium-build-') as temporary:
        events = Path(temporary) / 'events.json'
        subprocess.run([
            *bazel, 'build', *flags, '--//tools/ci:revision=' + revision,
            '--build_event_json_file=' + str(events),
            '--nobuild_event_json_file_path_conversion', label,
        ], cwd=ROOT, check=True)
        outputs = artifact_outputs(events, label)
        destination.mkdir(parents=True, exist_ok=True)
        for source in outputs:
            shutil.copyfile(source, destination / source.name)
    return destination / ('chromium-' + target['id'] + '.tar.gz')


def artifact_outputs(events, label):
    """Read this target's default output group from the completed build."""
    named_sets = {}
    roots = []
    completed = False
    with events.open() as stream:
        for line in stream:
            event = json.loads(line)
            if 'namedSetOfFiles' in event:
                named_sets[event['id']['namedSet']['id']] = event['namedSetOfFiles']
            if event.get('id', {}).get('targetCompleted', {}).get('label') == label:
                completed = event['completed']['success']
                for group in event['completed'].get('outputGroup', []):
                    if group['name'] == 'default':
                        roots.extend(item['id'] for item in group.get('fileSets', []))
    files = set()
    visited = set()
    while roots:
        identifier = roots.pop()
        if identifier in visited:
            continue
        visited.add(identifier)
        group = named_sets[identifier]
        roots.extend(item['id'] for item in group.get('fileSets', []))
        for item in group.get('files', []):
            uri = urlparse(item['uri'])
            if uri.scheme != 'file' or uri.netloc:
                raise ValueError('Artifact outputs must be downloaded locally')
            files.add(Path(unquote(uri.path)))
    name = 'chromium-' + label.rsplit(':', 1)[1].removesuffix('_archive') + '.tar.gz'
    if not completed or {path.name for path in files} != {name, name + '.sha256'} or len(files) != 2:
        raise ValueError('Build did not produce exactly one archive and checksum')
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['matrix', 'build', 'package', 'package-payload', 'stamp-payload', 'smoke'])
    parser.add_argument('--platform', choices=sorted(PLATFORMS))
    parser.add_argument('--revision')
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--artifact', type=Path)
    parser.add_argument('--payload', type=Path)
    parser.add_argument('--screenshots', type=Path, help='Rendering evidence directory for smoke tests')
    parser.add_argument('--buildbuddy-hosted', action='store_true',
                        help='Use credentials injected by the BuildBuddy workflow runner')
    args = parser.parse_args()
    if args.command == 'matrix':
        print(json.dumps({'include': CONFIGURATION['platforms']}, separators=(',', ':')))
        return
    if args.command == 'package-payload':
        if not args.platform or not args.bundle or not args.payload:
            parser.error('--platform, --bundle and --payload are required')
        print(package_payload(args.bundle, args.payload, PLATFORMS[args.platform]))
        return
    if not args.platform or not args.revision or not args.directory:
        parser.error('--platform, --revision and --directory are required')
    target = PLATFORMS[args.platform]
    if args.command == 'stamp-payload':
        if not args.payload:
            parser.error('--payload is required')
        print(stamp_payload(args.payload, args.directory, target, args.revision))
    elif args.command == 'build':
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
