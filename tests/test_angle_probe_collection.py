from pathlib import Path
import struct
import tempfile
import unittest

from tools.ci.collect_allocator_probes import collect_angle


def arm64_binary(path):
    path.write_bytes(struct.pack('<II', 0xfeedfacf, 0x0100000c) + bytes(24))
    return path


class ANGLEProbeCollectionTest(unittest.TestCase):
    def test_keeps_both_dylibs_next_to_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [arm64_binary(root / name)
                     for name in ['probe', 'libEGL.dylib', 'libGLESv2.dylib']]
            output = root / 'collected'
            collect_angle(files, 'darwin-arm64', output)
            self.assertEqual({file.name for file in output.iterdir()},
                             {'angle-darwin-arm64', 'libEGL.dylib', 'libGLESv2.dylib'})

    def test_missing_gles_library_leaves_no_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [arm64_binary(root / name) for name in ['probe', 'libEGL.dylib']]
            output = root / 'collected'
            with self.assertRaisesRegex(ValueError, 'both dylibs'):
                collect_angle(files, 'darwin-arm64', output)
            self.assertFalse(output.exists())
