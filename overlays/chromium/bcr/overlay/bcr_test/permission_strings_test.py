# SPDX-License-Identifier: Apache-2.0
"""Check Blink's native locale lookup against generated GRIT pack contents."""

from pathlib import Path
import re
import subprocess
import sys
import unittest

from grit.format import data_pack
from python.runfiles import runfiles


class PermissionStringsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resolver = runfiles.Create()
        cls.driver, base, generated, pack, french = (
            Path(resolver.Rlocation(path)) for path in sys.argv[1:])

        def header(path):
            return {name: int(value) for name, value in re.findall(
                r'^#define\s+(\w+)\s+(\d+)\s*$', path.read_text(), re.M)}

        cls.base = header(base)
        cls.generated = header(generated)
        def strings(path):
            result = data_pack.ReadDataPack(str(path))
            encoding = {data_pack.UTF8: 'utf-8', data_pack.UTF16: 'utf-16-le'}[result.encoding]
            return {resource: value.decode(encoding) for resource, value in result.resources.items()}

        cls.strings = strings(pack)
        cls.french = strings(french)

    def lookup(self, locale, resource):
        result = subprocess.run([self.driver, locale, str(resource)],
                                check=True, capture_output=True, text=True)
        return None if result.stdout == 'missing' else int(result.stdout)

    def test_french_translation(self):
        name = 'IDS_PERMISSION_REQUEST_CAMERA'
        translated = self.lookup('fr', self.base[name])
        self.assertEqual(translated, self.generated[name + '_fr'])
        text = self.strings[translated]
        self.assertEqual(text, "Utiliser l'appareil photo")
        self.assertEqual(text, self.french[self.base[name]])

    def test_language_aliases(self):
        name = 'IDS_PERMISSION_REQUEST_CAMERA'
        for locale, suffix, text in [
            ('en', 'en_GB', 'Use camera'),
            ('pt', 'pt_PT', 'Usar câmara'),
            ('zh', 'zh_CN', '使用摄像头'),
        ]:
            with self.subTest(locale=locale):
                translated = self.lookup(locale, self.base[name])
                self.assertEqual(translated, self.generated[name + '_' + suffix])
                self.assertEqual(self.strings[translated], text)

    def test_missing_language_and_message(self):
        resource = self.base['IDS_PERMISSION_REQUEST_CAMERA']
        self.assertIsNone(self.lookup('xx-YY', resource))
        self.assertIsNone(self.lookup('', resource))
        self.assertIsNone(self.lookup('fr', 0))


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
