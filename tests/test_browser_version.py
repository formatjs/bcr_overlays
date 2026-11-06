# SPDX-License-Identifier: MIT
import ctypes
from contextlib import nullcontext
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from overlays.chromium.tools.check_browser import windows_version


class WindowsBrowserVersionTest(unittest.TestCase):
    def version_api(self, signature=0xFEEF04BD):
        fixed = struct.pack(
            '<13I', signature, 0x10000, 9 << 16 | 8, 7 << 16 | 6,
            142 << 16, 7444 << 16 | 59, 0, 0, 0, 0, 0, 0, 0)
        translation = struct.pack('<HH', 0x0411, 0x04b0)
        product = 'Chromium\0'.encode('utf-16-le')
        payload = fixed + translation + product
        resources = {
            '\\': (0, 52),
            '\\VarFileInfo\\Translation': (52, 4),
            '\\StringFileInfo\\041104b0\\ProductName': (56, 9),
        }

        def load(path, handle, size, data):
            ctypes.memmove(data, payload, size)
            return 1

        def query(data, key, pointer, length):
            offset, size = resources[key]
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(data) + offset
            ctypes.cast(length, ctypes.POINTER(ctypes.c_uint32))[0] = size
            return 1

        api = mock.Mock()
        api.GetFileVersionInfoSizeW.return_value = len(payload)
        api.GetFileVersionInfoW.side_effect = load
        api.VerQueryValueW.side_effect = query
        return api

    def test_reads_product_name_and_full_product_version(self):
        api = self.version_api()
        with mock.patch.object(ctypes, 'WinDLL', return_value=api, create=True):
            self.assertEqual(windows_version(Path('chrome.exe')), 'Chromium 142.0.7444.59')

    def test_rejects_invalid_fixed_version_resource(self):
        with mock.patch.object(ctypes, 'WinDLL', return_value=self.version_api(0), create=True):
            with self.assertRaisesRegex(ValueError, 'invalid Windows version resource'):
                windows_version(Path('chrome.exe'))

    def test_rendering_uses_windows_resource_version_before_launch(self):
        from tools.ci import check_rendering
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch('tools.ci.check_rendering.serve_page',
                           return_value=nullcontext(('http://127.0.0.1/', set()))), \
                mock.patch('overlays.chromium.tools.check_browser.sys.platform', 'win32'), \
                mock.patch('overlays.chromium.tools.check_browser.windows_version',
                           side_effect=OSError('missing PE version')), \
                mock.patch('tools.ci.check_rendering.run',
                           side_effect=AssertionError('unsupported Windows --version launch')):
            with self.assertRaisesRegex(OSError, 'missing PE version'):
                check_rendering.check(Path('chrome.exe'), Path(directory) / 'screenshots')


if __name__ == '__main__':
    unittest.main()
