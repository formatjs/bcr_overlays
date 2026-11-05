import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUNNER = (Path(__file__).resolve().parents[1] /
          'overlays/chromium/bcr/overlay/native/python_action.py')


class ChromiumPythonActionTest(unittest.TestCase):
    def test_stages_imports_response_file_and_multiple_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'helper.py').write_text('VALUE = "declared import"\n')
            (root / 'generator.py').write_text('''import helper, pathlib, shlex, sys
arguments = shlex.split(pathlib.Path(sys.argv[1]).read_text())
pathlib.Path('gen/first.txt').write_text(helper.VALUE)
pathlib.Path('gen/second.txt').write_text(arguments[0])
''')
            manifest = {
                'inputs': [['generator.py', 'scripts/generator.py'],
                           ['helper.py', 'scripts/helper.py']],
                'outputs': [['first.txt', 'gen/first.txt'],
                            ['second.txt', 'gen/second.txt']],
                'build_dir': 'out/import',
                'script': 'scripts/generator.py',
                'args': ['{{response_file_name}}'],
                'response_file_contents': ['LABEL="contains spaces"'],
            }
            (root / 'manifest.json').write_text(json.dumps(manifest))
            result = subprocess.run([sys.executable, str(RUNNER), 'manifest.json'],
                                    cwd=root, capture_output=True, text=True,
                                    env=dict(os.environ, PYTHONSAFEPATH='1'))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'first.txt').read_text(), 'declared import')
            self.assertEqual((root / 'second.txt').read_text(), 'LABEL="contains spaces"')

    def test_rejects_output_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {'inputs': [], 'build_dir': 'out/import',
                        'outputs': [['result', '../../escape']]}
            (root / 'manifest.json').write_text(json.dumps(manifest))
            result = subprocess.run([sys.executable, str(RUNNER), 'manifest.json'],
                                    cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('invalid logical path', result.stderr)
            self.assertFalse((root / 'escape').exists())


if __name__ == '__main__':
    unittest.main()
