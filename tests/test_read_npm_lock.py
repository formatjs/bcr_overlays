import unittest

from tools.read_npm_lock import dependency_closure


def package(version, dependencies=None):
    return {'version': version, 'resolved': 'https://registry.npmjs.org/test/-/test.tgz',
            'integrity': 'sha512-test', 'dependencies': dependencies or {}}


class ReadNpmLockTest(unittest.TestCase):
    def test_resolves_nested_packages_and_scoped_hoisted_dependencies(self):
        lock = {'lockfileVersion': 3, 'packages': {
            'node_modules/tool': package('1', {'library': '1', '@scope/helper': '2'}),
            'node_modules/library': package('9'),
            'node_modules/tool/node_modules/library': package('1'),
            'node_modules/@scope/helper': package('2', {'codec': '3'}),
            'node_modules/codec': package('3'),
        }}
        result = dependency_closure(lock, 'tool')
        self.assertNotIn('node_modules/library', result)
        self.assertEqual(result['node_modules/tool/node_modules/library']['version'], '1')
        self.assertIn('node_modules/@scope/helper', result)
        self.assertIn('node_modules/codec', result)

    def test_rejects_unlocked_dependencies_and_install_scripts(self):
        lock = {'lockfileVersion': 3, 'packages': {
            'node_modules/tool': package('1', {'missing': '1'}),
        }}
        with self.assertRaisesRegex(ValueError, 'unresolved dependency'):
            dependency_closure(lock, 'tool')
        lock['packages']['node_modules/tool'] = package('1')
        lock['packages']['node_modules/tool']['hasInstallScript'] = True
        with self.assertRaisesRegex(ValueError, 'unsupported package setup'):
            dependency_closure(lock, 'tool')


if __name__ == '__main__':
    unittest.main()
