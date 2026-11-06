from pathlib import Path
import struct
import tempfile
import unittest

from tools.ci.collect_allocator_probes import collect_v8


class V8ProbeCollectionTest(unittest.TestCase):
    def test_keeps_startup_data_next_to_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / 'probe'
            executable.write_bytes(struct.pack('<II', 0xfeedfacf, 0x0100000c) + bytes(24))
            icu = root / 'icudtl.dat'
            icu.write_bytes(b'ICU data')
            snapshot = root / 'snapshot_blob.bin'
            snapshot.write_bytes(b'ARM64 snapshot')
            output = root / 'collected'
            collect_v8([executable, snapshot, icu], 'darwin-arm64', output)
            self.assertEqual({file.name for file in output.iterdir()},
                             {'v8-darwin-arm64', 'icudtl.dat', 'snapshot_blob.bin'})
            self.assertEqual((output / 'snapshot_blob.bin').read_bytes(), b'ARM64 snapshot')
            self.assertEqual((output / 'icudtl.dat').read_bytes(), b'ICU data')

    def test_missing_startup_data_leaves_no_partial_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'collected'
            with self.assertRaisesRegex(ValueError, 'ICU data and snapshot'):
                collect_v8([], 'darwin-arm64', output)
            self.assertFalse(output.exists())
