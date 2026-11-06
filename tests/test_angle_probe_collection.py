from pathlib import Path
import struct
import tempfile
import unittest

from tools.ci.collect_allocator_probes import collect_angle


def arm64_binary(path):
    path.write_bytes(struct.pack('<II', 0xfeedfacf, 0x0100000c) + bytes(24))
    return path


def windows_binary(path, machine):
    data = bytearray(256)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 128)
    data[128:132] = b'PE\0\0'
    struct.pack_into('<H', data, 132, machine)
    path.write_bytes(data)
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

    def test_windows_dlls_stay_next_to_probe(self):
        for arch, machine in [('amd64', 0x8664), ('arm64', 0xaa64)]:
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                files = [windows_binary(root / name, machine)
                         for name in ['probe.exe', 'libEGL.dll', 'libGLESv2.dll']]
                output = root / 'collected'
                collect_angle(files, 'windows-' + arch, output)
                self.assertEqual({file.name for file in output.iterdir()},
                                 {'angle-windows-' + arch + '.exe', 'libEGL.dll', 'libGLESv2.dll'})

    def test_mismatched_windows_dll_leaves_no_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [windows_binary(root / 'probe.exe', 0xaa64),
                     windows_binary(root / 'libEGL.dll', 0xaa64),
                     windows_binary(root / 'libGLESv2.dll', 0x8664)]
            output = root / 'collected'
            with self.assertRaisesRegex(ValueError, 'matching executable'):
                collect_angle(files, 'windows-arm64', output)
            self.assertFalse(output.exists())
