import io
import os
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest import mock

from tools.ci.chromium import PLATFORMS, ROOT, binary_platform, build, checksum, package, unpack


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

    def test_hosted_build_uses_managed_credentials_and_packages_output(self):
        environment = {'BUILDBUDDY_CI_RUNNER_ABSPATH': '/runner/ci_runner'}
        with mock.patch.dict(os.environ, environment, clear=True), \
                mock.patch('tools.ci.chromium.subprocess.run') as execute, \
                mock.patch('tools.ci.chromium.subprocess.check_output',
                           return_value=str(self.bundle) + '\n') as query:
            archive = build(self.target, self.root / 'artifacts', REVISION, hosted=True)
        command = ['bazel', 'build', '--config=browser', '--config=buildbuddy',
                   '//tools/ci:linux-amd64']
        execute.assert_called_once_with(command, cwd=ROOT, check=True)
        query.assert_called_once_with(
            ['bazel', 'cquery', '--config=browser', '--config=buildbuddy',
             '--output=files', '//tools/ci:linux-amd64'], cwd=ROOT, text=True,
        )
        destination = unpack(archive, self.root / 'hosted-output', self.target, REVISION)
        self.assertEqual((destination / 'resources.pak').read_bytes(), b'locale data')

    def test_hosted_mode_requires_managed_runner(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch('tools.ci.chromium.subprocess.run') as execute:
            with self.assertRaisesRegex(ValueError, 'BuildBuddy workflow runner'):
                build(self.target, self.root / 'artifacts', REVISION, hosted=True)
        execute.assert_not_called()
if __name__ == '__main__':
    unittest.main()
