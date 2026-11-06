from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'overlays/chromium/tools'))
from import_platform_base import copy_package_inputs
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
