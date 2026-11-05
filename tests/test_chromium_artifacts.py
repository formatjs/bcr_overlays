import io
import json
import os
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest import mock

from tools.ci.chromium import PLATFORMS, ROOT, binary_platform, build, checksum, package, unpack, artifact_outputs


REVISION = '1' * 40


def elf(machine=62):
    header = bytearray(64)
    header[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<H', header, 18, machine)
    return header


class ArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bundle = self.root / 'input'
        self.bundle.mkdir()
        (self.bundle / 'chrome').write_bytes(elf())
        (self.bundle / 'chrome').chmod(0o755)
        (self.bundle / 'resources.pak').write_bytes(b'locale data')
        self.target = PLATFORMS['linux-amd64']

    def archive(self):
        return package(self.bundle, self.root / 'artifacts', self.target, REVISION)

    def test_round_trip_preserves_executable_and_resources(self):
        destination = unpack(self.archive(), self.root / 'relocated', self.target, REVISION)
        self.assertEqual((destination / 'resources.pak').read_bytes(), b'locale data')
        self.assertEqual(binary_platform(destination / 'chrome'), ('linux', 'amd64'))
        self.assertTrue(os.access(destination / 'chrome', os.X_OK))

    def test_wrong_architecture_cannot_be_packaged(self):
        with self.assertRaisesRegex(ValueError, 'Wrong artifact architecture'):
            package(self.bundle, self.root / 'artifacts', PLATFORMS['linux-arm64'], REVISION)

    def test_corruption_is_rejected_before_extraction(self):
        archive = self.archive()
        with archive.open('ab') as output:
            output.write(b'corrupted')
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            unpack(archive, self.root / 'relocated', self.target, REVISION)
        self.assertFalse((self.root / 'relocated').exists())

    def test_artifact_from_another_commit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'provenance'):
            unpack(self.archive(), self.root / 'relocated', self.target, '2' * 40)

    def test_archive_cannot_escape_destination(self):
        archive = self.root / 'escape.tar.gz'
        with tarfile.open(archive, 'w:gz') as output:
            member = tarfile.TarInfo('../escaped')
            member.size = 4
            output.addfile(member, io.BytesIO(b'bad!'))
        archive.with_suffix('.gz.sha256').write_text(checksum(archive))
        with self.assertRaisesRegex(ValueError, 'Invalid artifact path'):
            unpack(archive, self.root / 'relocated', self.target, REVISION)
        self.assertFalse((self.root / 'escaped').exists())

    def test_windows_and_macos_headers(self):
        cases = []
        for machine, arch in [(0x8664, 'amd64'), (0xAA64, 'arm64')]:
            header = bytearray(134)
            header[:2] = b'MZ'
            struct.pack_into('<I', header, 60, 128)
            header[128:132] = b'PE\0\0'
            struct.pack_into('<H', header, 132, machine)
            cases.append((header, ('windows', arch)))
        header = bytearray(64)
        header[:4] = b'\xcf\xfa\xed\xfe'
        struct.pack_into('<I', header, 4, 0x100000C)
        cases.append((header, ('darwin', 'arm64')))
        cases.append((elf(183), ('linux', 'arm64')))
        for index, (header, expected) in enumerate(cases):
            with self.subTest(expected=expected):
                binary = self.root / f'binary-{index}'
                binary.write_bytes(header)
                self.assertEqual(binary_platform(binary), expected)

    def test_hosted_build_uses_one_invocation_and_cached_archive(self):
        source = self.archive()
        sidecar = source.with_suffix('.gz.sha256')
        label = '//tools/ci:linux-amd64_archive'

        def execute(command, **kwargs):
            self.assertEqual(command[:4], ['bazel', 'build', '--config=browser', '--config=buildbuddy'])
            self.assertIn('--//tools/ci:revision=' + REVISION, command)
            self.assertEqual(command[-1], label)
            self.assertEqual(kwargs, {'cwd': ROOT, 'check': True})
            events = Path(next(value.split('=', 1)[1] for value in command
                               if value.startswith('--build_event_json_file=')))
            events.write_text('\n'.join(json.dumps(event) for event in [
                {'id': {'namedSet': {'id': 'artifacts'}}, 'namedSetOfFiles': {
                    'files': [{'uri': item.as_uri()} for item in [source, sidecar]]}},
                {'id': {'targetCompleted': {'label': label}}, 'completed': {
                    'success': True, 'outputGroup': [{'name': 'default', 'fileSets': [{'id': 'artifacts'}]}]}},
            ]))

        environment = {'BUILDBUDDY_CI_RUNNER_ABSPATH': '/runner/ci_runner'}
        with mock.patch.dict(os.environ, environment, clear=True), \
                mock.patch('tools.ci.chromium.subprocess.run', side_effect=execute) as process:
            archive = build(self.target, self.root / 'hosted-artifacts', REVISION, hosted=True)
        self.assertEqual(process.call_count, 1)
        destination = unpack(archive, self.root / 'hosted-output', self.target, REVISION)
        self.assertEqual((destination / 'resources.pak').read_bytes(), b'locale data')

    def test_archive_bytes_ignore_input_mtime_and_non_executable_permissions(self):
        first = package(self.bundle, self.root / 'first', self.target, REVISION).read_bytes()
        for path in self.bundle.rglob('*'):
            os.utime(path, (1234567890, 1234567890))
        (self.bundle / 'resources.pak').chmod(0o600)
        second = package(self.bundle, self.root / 'second', self.target, REVISION).read_bytes()
        self.assertEqual(first, second)
        with tarfile.open(fileobj=io.BytesIO(second), mode='r:gz') as archive:
            self.assertTrue(all(item.mtime == item.uid == item.gid == 0 for item in archive))

    def test_failed_or_remote_only_build_outputs_are_rejected(self):
        events = self.root / 'events.json'
        label = '//tools/ci:linux-amd64_archive'
        for success, uri in [(False, (self.root / 'archive').as_uri()), (True, 'bytestream://remote/archive')]:
            events.write_text('\n'.join(json.dumps(event) for event in [
                {'id': {'namedSet': {'id': 'files'}}, 'namedSetOfFiles': {'files': [{'uri': uri}]}},
                {'id': {'targetCompleted': {'label': label}}, 'completed': {
                    'success': success, 'outputGroup': [{'name': 'default', 'fileSets': [{'id': 'files'}]}]}},
            ]))
            with self.subTest(success=success), self.assertRaises(ValueError):
                artifact_outputs(events, label)

    def test_hosted_mode_requires_managed_runner(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch('tools.ci.chromium.subprocess.run') as execute:
            with self.assertRaisesRegex(ValueError, 'BuildBuddy workflow runner'):
                build(self.target, self.root / 'artifacts', REVISION, hosted=True)
        execute.assert_not_called()
if __name__ == '__main__':
    unittest.main()
