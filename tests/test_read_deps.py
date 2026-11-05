"""DEPS resolution preserves pins without executing upstream Python."""

from pathlib import Path
import tempfile
import unittest

from tools.read_deps import parse_deps


class ReadDepsTest(unittest.TestCase):
    def test_resolves_shared_pins_and_keeps_conditions_as_data(self):
        result = parse_deps('''
vars = {
    'origin': 'https://example.test',
    'mirror': Var('origin') + '/mirror',
    'revision': '0123456789abcdef',
    'checkout_android': False,
    'board': Str(''),
}
deps = {
    'src/library': {
        'url': Var('mirror') + '/library.git@' + Var('revision'),
        'condition': 'checkout_android',
    },
    'src/tool': {
        'packages': [{'package': 'tool/${{platform}}', 'version': Var('revision')}],
        'dep_type': 'cipd',
    },
    'src/templated': '{mirror}/library.git@{revision}',
}
gclient_gn_args = ['checkout_android', 'board']
''')
        self.assertEqual(result["deps"], {
            "src/library": {
                "url": "https://example.test/mirror/library.git@0123456789abcdef",
                "condition": "checkout_android",
            },
            "src/tool": {
                "packages": [{"package": "tool/${{platform}}", "version": "0123456789abcdef"}],
                "dep_type": "cipd",
            },
            "src/templated": "https://example.test/mirror/library.git@0123456789abcdef",
        })
        self.assertEqual(result["gclient_gn_args"], {"checkout_android": False, "board": ""})

    def test_rejects_python_calls_mutations_and_variable_cycles(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "executed"
            sources = [
                f"vars = {{'bad': __import__('pathlib').Path({str(sentinel)!r}).touch()}}\ndeps = {{}}",
                "vars = {}\ndeps = {}\ndeps.update({'src/mutated': 'url@pin'})",
                "vars = {'first': Var('second'), 'second': Var('first')}\ndeps = {}",
                "vars = {}\ndeps = {'src/lib': '{missing}/lib@pin'}",
                "vars = {'origin': '{origin}'}\ndeps = {'src/lib': '{origin}/lib@pin'}",
            ]
            for source in sources:
                with self.subTest(source=source), self.assertRaises(ValueError):
                    parse_deps(source)
                self.assertFalse(sentinel.exists())


if __name__ == "__main__":
    unittest.main()
