import importlib.util
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'overlays/chromium/bcr/overlay/native/assemble_runtime.py'
SPEC = importlib.util.spec_from_file_location('assemble_runtime', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RuntimeBundleTest(unittest.TestCase):
    def test_nested_framework_remains_relocatable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / 'binary'
            binary.write_bytes(b'framework executable')
            binary.chmod(0o755)
            framework = root / 'framework'
            MODULE.assemble({
                'inputs': [[str(binary), 'Versions/142/Chromium Framework']],
                'output': str(framework),
                'symlinks': {'Versions/Current': '142',
                             'Chromium Framework': 'Versions/Current/Chromium Framework'},
            })
            app = root / 'Chromium.app'
            MODULE.assemble({
                'inputs': [[str(framework), 'Contents/Frameworks/Chromium Framework.framework'],
                           [str(binary), 'Contents/MacOS/Chromium']],
                'output': str(app),
            })
            moved = root / 'relocated.app'
            shutil.move(app, moved)
            installed = moved / 'Contents/Frameworks/Chromium Framework.framework'
            self.assertEqual((installed / 'Chromium Framework').read_bytes(), binary.read_bytes())
            self.assertEqual(os.readlink(installed / 'Versions/Current'), '142')
            self.assertTrue((moved / 'Contents/MacOS/Chromium').stat().st_mode & stat.S_IXUSR)

    def test_directory_cannot_hide_another_declared_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'directory'
            directory.mkdir()
            binary = root / 'binary'
            binary.touch()
            with self.assertRaisesRegex(ValueError, 'overlapping runtime paths'):
                MODULE.assemble({'inputs': [[str(directory), 'Framework'],
                                            [str(binary), 'Framework-copy'],
                                            [str(binary), 'Framework/binary']],
                                 'output': str(root / 'output')})

    def test_symlinks_stay_inside_bundle(self):
        for target in ['/host/library', '../../host/library']:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(ValueError, 'invalid runtime symlink'):
                    MODULE.assemble({'inputs': [], 'output': temporary,
                                     'symlinks': {'Versions/Current': target}})
