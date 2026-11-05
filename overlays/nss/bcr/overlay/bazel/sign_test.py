"""Exercise NSS signing after remote-style input materialization."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from python.runfiles import runfiles
from sign import sign


class SignTest(unittest.TestCase):
    def test_regular_files(self):
        resolver = runfiles.Create()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copied = []
            for index, name in enumerate(RUNTIME):
                source = Path(resolver.Rlocation(name))
                target = root / str(index) / source.name
                target.parent.mkdir()
                shutil.copyfile(source, target)
                target.chmod(source.stat().st_mode)
                self.assertFalse(target.is_symlink())
                copied.append(target)
            tool = next(path for path in copied if path.name == "shlibsign")
            library = root / "module.so"
            shutil.copyfile(resolver.Rlocation(MODULE), library)
            output = root / "module.chk"
            sign(tool, library, output, [path for path in copied if path.suffix == ".so"])
            self.assertGreater(output.stat().st_size, 0)


if __name__ == "__main__":
    RUNTIME = sys.argv[1:-1]
    MODULE = sys.argv[-1]
    unittest.main(argv=[sys.argv[0]])
