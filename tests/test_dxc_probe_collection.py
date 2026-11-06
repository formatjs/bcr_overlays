from pathlib import Path
import struct
import tempfile
import unittest

from tools.ci.collect_allocator_probes import collect_dxc


def windows_binary(path, machine):
    data = bytearray(256)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 128)
    data[128:132] = b'PE\0\0'
    struct.pack_into('<H', data, 132, machine)
    path.write_bytes(data)
    return path


class DXCProbeCollectionTest(unittest.TestCase):
    def test_dll_stays_next_to_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = windows_binary(root / 'probe.exe', 0xaa64)
            library = windows_binary(root / 'dxcompiler.dll', 0xaa64)
            output = root / 'collected'
            collect_dxc([library, executable], 'windows-arm64', output)
            self.assertEqual({file.name for file in output.iterdir()},
                             {'dxc-windows-arm64.exe', 'dxcompiler.dll'})

    def test_mismatched_dll_leaves_no_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = windows_binary(root / 'probe.exe', 0xaa64)
            library = windows_binary(root / 'dxcompiler.dll', 0x8664)
            output = root / 'collected'
            with self.assertRaisesRegex(ValueError, 'matching Windows'):
                collect_dxc([executable, library], 'windows-arm64', output)
            self.assertFalse(output.exists())

    def test_dll_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'collected'
            with self.assertRaisesRegex(ValueError, 'dxcompiler.dll'):
                collect_dxc([], 'windows-amd64', output)
            self.assertFalse(output.exists())
