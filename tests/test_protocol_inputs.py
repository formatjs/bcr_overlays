from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'overlays/chromium/tools'))
from import_cpp_layer import protocol_inputs


class ProtocolInputsTest(unittest.TestCase):
    def test_recursive_includes_keep_logical_paths_through_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'checkout'
            shared = Path(directory) / 'shared'
            root.mkdir()
            shared.mkdir()
            (root / 'protocol').symlink_to(shared, target_is_directory=True)
            (shared / 'domains').mkdir()
            (shared / 'main.pdl').write_text('include domains/Child.pdl\n')
            (shared / 'domains/Child.pdl').write_text('include ../Common.pdl\n')
            (shared / 'Common.pdl').write_text('domain Common\n')
            self.assertEqual(protocol_inputs(root, ['//protocol/main.pdl']), {
                '//protocol/main.pdl', '//protocol/domains/Child.pdl', '//protocol/Common.pdl',
            })

    def test_include_cannot_escape_checkout_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'checkout'
            root.mkdir()
            (root / 'main.pdl').write_text('include ../outside.pdl\n')
            (root.parent / 'outside.pdl').write_text('domain Outside\n')
            with self.assertRaises(ValueError):
                protocol_inputs(root, ['//main.pdl'])
