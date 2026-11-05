from pathlib import Path
import sys
import unittest

from python.runfiles import runfiles


class GeneratorRuntimeTest(unittest.TestCase):
    def test_declared_sibling_data(self):
        output = Path(runfiles.Create().Rlocation(OUTPUT))
        self.assertEqual(output.read_text(), "declared runtime data\n")


if __name__ == "__main__":
    OUTPUT = sys.argv.pop(1)
    unittest.main()
