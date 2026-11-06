from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'overlays/chromium/tools'))
from import_platform_base import copy_package_inputs, write_host_support
import import_platform_base
sys.path.pop(0)


class PlatformPackageInputsTest(unittest.TestCase):
    def test_regeneration_preserves_rules_and_removes_stale_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            captured, maintained = root / 'captured', root / 'maintained'
            for directory in [captured / 'build', maintained / 'build', maintained / 'obsolete']:
                directory.mkdir(parents=True)
            block = '# BEGIN BROWSER INPUTS\nexports_files(["{}"] )\n# END BROWSER INPUTS\n'
            (captured / 'build/BUILD.bazel').write_text(
                'cc_library(name = "adapter", copts = ["-O2"])\n' + block.format('new.plist'))
            (maintained / 'build/BUILD.bazel').write_text(
                'cc_library(name = "adapter", copts = ["-O3"])\n' + block.format('old.plist'))
            (maintained / 'obsolete/BUILD.bazel').write_text(
                'filegroup(name = "keep")\n' + block.format('stale.h'))
            copy_package_inputs(captured, maintained, ['browser'])
            result = (maintained / 'build/BUILD.bazel').read_text()
            self.assertIn('copts = ["-O3"]', result)
            self.assertIn('new.plist', result)
            self.assertNotIn('old.plist', result)
            self.assertEqual((maintained / 'obsolete/BUILD.bazel').read_text(), 'filegroup(name = "keep")\n')

    def test_host_alias_uses_gn_identity_when_layer_ownership_differs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native = root / 'bcr/overlay/native'
            cross = root / 'windows/native'
            native.mkdir(parents=True)
            cross.mkdir(parents=True)
            record = 'LIBRARIES = {\n    "//components/crash/core/common:common": {\n        "name": "{}",\n    },\n}\n'
            (native / 'gpu_service_sources.bzl').write_text(record.replace('{}', 'gpu_service_common'))
            (cross / 'gfx_sources.bzl').write_text(record.replace('{}', 'gfx_common'))
            with patch.object(import_platform_base, 'ROOT', root):
                write_host_support(root / 'windows', 'windows_arm64')
            aliases = []
            environment = {
                'load': lambda *args, **kwargs: None,
                '_cc_library': lambda **kwargs: None,
                'native': SimpleNamespace(alias=lambda **kwargs: aliases.append(kwargs),
                                          package_name=lambda: 'native'),
                'select': lambda values: values['//conditions:default'],
            }
            exec((cross / 'host_support.bzl').read_text(), environment)
            environment['platform_cc_library'](name='gfx_common')
            self.assertEqual(aliases[-1]['actual'], '@chromium//native:gpu_service_common')
            environment['select'] = lambda values: values['@platforms//os:windows']
            environment['platform_cc_library'](name='gfx_common')
            self.assertEqual(aliases[-1]['actual'], ':gfx_common_windows')
