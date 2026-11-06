from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'overlays/chromium/tools'))
from import_cpp_layer import resource_asset_inputs, declare_message_compiler_assets


class WindowsResourceInputsTest(unittest.TestCase):
    def test_nested_resources_keep_windows_relative_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'app/theme').mkdir(parents=True)
            (source / 'app/main.rc').write_text('#include "common.rc"\n')
            (source / 'app/common.rc').write_text(r'ICON "theme\chrome.ico"' + '\n')
            (source / 'app/theme/chrome.ico').write_bytes(b'icon')
            self.assertEqual(resource_asset_inputs(source, '//app/main.rc'), {
                '//app/common.rc', '//app/theme/chrome.ico',
            })

    def test_unavailable_brand_assets_do_not_hide_available_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'main.rc').write_text('ICON "proprietary.ico"\nICON "chromium.ico"\n')
            (source / 'chromium.ico').write_bytes(b'icon')
            self.assertEqual(resource_asset_inputs(source, '//main.rc'), {'//chromium.ico'})

    def test_resources_cannot_import_files_outside_source_root(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            source = parent / 'src'
            source.mkdir()
            (parent / 'outside.ico').write_bytes(b'outside')
            (source / 'main.rc').write_text('ICON "../outside.ico"\n')
            self.assertEqual(resource_asset_inputs(source, '//main.rc'), set())

    def test_message_compiler_declares_binary_table_from_checked_in_rc(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            checked = source / 'third_party/win_build_output/mc/chrome/common/win'
            checked.mkdir(parents=True)
            (checked / 'messages.rc').write_text('LANGUAGE 0x9,0x1\n1 11 "MSG00409.bin"\n')
            (checked / 'MSG00409.bin').write_bytes(b'message table')
            prefix = '//out/bazel-import/'
            outputs = ['gen/chrome/common/win/messages.h', 'gen/chrome/common/win/messages.rc']
            target = {'script': '//build/win/message_compiler.py',
                      'args': ['environment.arm64', '-h', 'gen/chrome/common/win',
                               '-r', 'gen/chrome/common/win', '-u', '{{source}}'],
                      'outputs': [prefix + path for path in outputs],
                      'source_outputs': {'//chrome/common/win/messages.mc': outputs}}
            declare_message_compiler_assets({'messages': target}, source)
            binary = 'gen/chrome/common/win/MSG00409.bin'
            self.assertIn(prefix + binary, target['outputs'])
            self.assertIn(binary, target['source_outputs']['//chrome/common/win/messages.mc'])
