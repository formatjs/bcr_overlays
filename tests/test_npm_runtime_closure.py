import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


path = Path(__file__).resolve().parents[1] / 'overlays/chromium/tools/npm_runtime_closure.py'
spec = importlib.util.spec_from_file_location('npm_runtime_closure', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RuntimeClosureTest(unittest.TestCase):
    def test_nested_versions_scoped_packages_and_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packages = {
                'tool': {'dependencies': {'shared': '*', '@scope/helper': '*'},
                         'devDependencies': {'unused': '*'},
                         'optionalDependencies': {'unavailable': '*'}},
                'tool/node_modules/shared': {},
                'shared': {'dependencies': {'must-not-be-used': '*'}},
                '@scope/helper': {'dependencies': {'leaf': '*'}},
                'leaf': {},
            }
            for name, metadata in packages.items():
                package = root / name
                package.mkdir(parents=True)
                (package / 'package.json').write_text(json.dumps(metadata))
            self.assertEqual(module.runtime_closure(root, ['tool']), [
                '@scope/helper', 'leaf', 'tool', 'tool/node_modules/shared',
            ])
            (root / 'leaf/package.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing runtime dependency leaf'):
                module.runtime_closure(root, ['tool'])
