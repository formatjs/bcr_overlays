import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from tools.ci import buildbuddy_artifacts, components
from tools.ci.chromium import checksum, unpack, PLATFORMS


REVISION = '1' * 40
TARGET = 'linux-amd64'


def probe(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = bytearray(64)
    header[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<H', header, 18, 62)
    path.write_bytes(header)
    path.chmod(0o755)


class ComponentHandoffTest(unittest.TestCase):
    def test_build_requires_hosted_runner_without_local_fallback(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(components.subprocess, 'run') as process:
            with self.assertRaisesRegex(ValueError, 'BuildBuddy workflow runner'):
                components.build(TARGET, Path('/unused'), REVISION)
        process.assert_not_called()

    def test_hosted_build_packages_relocatable_outputs_with_same_bazel_configuration(self):
        commands = []

        def execute(command, **kwargs):
            commands.append(command)
            self.assertTrue(kwargs['check'])
            if 'tools.ci.collect_allocator_probes' in command:
                destination = Path(command[command.index('--output') + 1])
                probe(destination / ('rust-' + TARGET))
                probe(destination / ('expat-' + TARGET))
                (destination / 'runtime.dat').write_bytes(b'relocated data')

        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.dict(os.environ, {'BUILDBUDDY_CI_RUNNER_ABSPATH': '/runner'}, clear=True), \
                mock.patch.object(components.subprocess, 'run', side_effect=execute):
            root = Path(temporary)
            archive = components.build(TARGET, root / 'artifacts', REVISION)
            self.assertEqual(commands[0], ['bazel', 'build', '--config=buildbuddy',
                                          '--//tools/ci:revision=' + REVISION,
                                          '//tools/ci:rust-linux-amd64', '//tools/ci:expat-linux-amd64'])
            self.assertIn('--bazel-arg=--config=buildbuddy', commands[1])
            output = unpack(archive, root / 'relocated', components.component_target(TARGET), REVISION)
            self.assertEqual((output / 'runtime.dat').read_bytes(), b'relocated data')
            self.assertTrue((output / ('rust-' + TARGET)).stat().st_mode & 0o111)
            for target, revision in [(PLATFORMS[TARGET], REVISION),
                                     (components.component_target(TARGET), '2' * 40)]:
                with self.subTest(target=target['id'], revision=revision), \
                        self.assertRaisesRegex(ValueError, 'provenance'):
                    unpack(archive, root / ('wrong-' + target['id'] + revision), target, revision)

    def test_component_download_requires_component_action_and_component_artifacts(self):
        payload = b'component archive bytes'
        name = 'chromium-components-' + TARGET + '.tar.gz'
        invocation = {'invocation': [{
            'commitSha': REVISION, 'repoUrl': 'https://github.com/formatjs/chromium.git',
            'pattern': 'Chromium components ' + TARGET, 'success': True,
            'invocationStatus': 'COMPLETE_INVOCATION_STATUS',
            'artifacts': [{'name': 'components/' + file,
                           'uri': 'bytestream://formatjs.buildbuddy.io/blobs/' + str(index)}
                          for index, file in enumerate([name, name + '.sha256'])],
        }]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / 'source'
            archive.write_bytes(payload)
            replies = [io.BytesIO(json.dumps(invocation).encode()), io.BytesIO(payload),
                       io.BytesIO((checksum(archive) + '\n').encode())]
            with mock.patch.object(buildbuddy_artifacts, 'api_request', side_effect=replies):
                buildbuddy_artifacts.download(
                    'https://formatjs.buildbuddy.io/invocation/01234567-89ab-cdef-0123-456789abcdef',
                    REVISION, TARGET, root / 'download', 'read-only-test-key', kind='components')
            self.assertEqual((root / 'download' / name).read_bytes(), payload)
        with self.assertRaisesRegex(ValueError, 'successful commit'):
            buildbuddy_artifacts.artifact_uris(invocation, REVISION, TARGET)
        invocation['invocation'][0]['pattern'] = 'Chromium ' + TARGET
        with self.assertRaisesRegex(ValueError, 'successful commit'):
            buildbuddy_artifacts.artifact_uris(invocation, REVISION, TARGET, kind='components')


if __name__ == '__main__':
    unittest.main()
