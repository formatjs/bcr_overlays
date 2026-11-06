from pathlib import Path
import sys
import unittest

from python.runfiles import runfiles


class GeneratorRuntimeTest(unittest.TestCase):
    def test_declared_sibling_data(self):
        for location in OUTPUTS:
            with self.subTest(location=location):
                output = Path(runfiles.Create().Rlocation(location))
                self.assertEqual(output.read_text(), "declared runtime data\n")


if __name__ == "__main__":
    OUTPUTS = sys.argv[1:]
    del sys.argv[1:]
    unittest.main()
