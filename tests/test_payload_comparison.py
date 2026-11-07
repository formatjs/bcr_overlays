import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.ci import compare_payloads as comparison
from tools.ci.chromium import PLATFORMS, stamp_payload
from tools.ci.compare_payloads import payload_digest


class PayloadComparisonTest(unittest.TestCase):
    def test_same_commit_cold_and_regular_builds_are_compared_independently(self):
        revision = '1' * 40
        platform = 'linux-amd64'
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch('sys.argv', ['compare', '--baseline', revision, '--revision', revision,
                                       '--revision-kind', 'cold-browser', '--platform', platform,
                                       '--directory', temporary]), \
                mock.patch.object(comparison, 'build_urls', side_effect=lambda rev, platforms, kind:
                                  {platform: 'https://example.test/' + kind}), \
                mock.patch.object(comparison, 'digest_artifact', side_effect=lambda url, rev, target, kind:
                                  {'sha256': kind, 'size_bytes': 100}) as digest:
            with self.assertRaisesRegex(ValueError, 'Browser payload bytes changed'):
                comparison.main()
            result = json.loads((Path(temporary) / 'payload-comparison.json').read_text())
            self.assertFalse(result['platforms'][platform]['payload_bytes_match'])
            digest.assert_has_calls([
                mock.call('https://example.test/browser', revision, platform, 'browser'),
                mock.call('https://example.test/cold-browser', revision, platform, 'cold-browser'),
            ], any_order=True)

    def archive(self, root, payload, revision):
        source = root / ('payload-' + revision + '.gz')
        source.write_bytes(gzip.compress(payload, mtime=0))
        return stamp_payload(source, root / revision, PLATFORMS['linux-amd64'], revision).read_bytes()

    def test_revision_changes_do_not_change_payload_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.archive(root, b'compiled browser bytes', '1' * 40)
            second = self.archive(root, b'compiled browser bytes', '2' * 40)
            changed = self.archive(root, b'different compiled browser bytes', '3' * 40)
            self.assertNotEqual(first, second)
            results = [payload_digest(io.BytesIO(data), hashlib.sha256(data).hexdigest(), revision * 40,
                                      'linux-amd64')
                       for data, revision in ((first, '1'), (second, '2'), (changed, '3'))]
            self.assertEqual(results[0], results[1])
            self.assertNotEqual(results[0], results[2])

    def test_checksum_and_stamp_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = self.archive(Path(temporary), b'compiled browser bytes', '1' * 40)
            checksum = hashlib.sha256(data).hexdigest()
            for content, expected, revision in ((data[:-5], checksum, '1' * 40),
                                                (data, '0' * 64, '1' * 40),
                                                (data, checksum, '2' * 40)):
                with self.subTest(revision=revision, truncated=len(content) != len(data)):
                    with self.assertRaises(ValueError):
                        payload_digest(io.BytesIO(content), expected, revision, 'linux-amd64')

    def test_unbounded_stamp_is_rejected_before_payload_processing(self):
        data = gzip.compress(b'x' * 100000, mtime=0)
        with self.assertRaisesRegex(ValueError, 'stamp exceeds'):
            payload_digest(io.BytesIO(data), hashlib.sha256(data).hexdigest(), '1' * 40, 'linux-amd64')


if __name__ == '__main__':
    unittest.main()
