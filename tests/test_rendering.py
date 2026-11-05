from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from tools.ci.check_rendering import compare


class RenderingComparisonTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.difference = Path(self.temporary.name) / 'diff.png'
        self.expected = Image.new('RGB', (100, 100), '#15243a')
        ImageDraw.Draw(self.expected).rectangle((20, 20, 80, 80), fill='#53d6bd')

    def test_identical_rendering_has_empty_difference(self):
        result = compare(self.expected, self.expected.copy(), self.difference)
        self.assertTrue(result['passed'])
        self.assertEqual(result['changed_pixels'], 0)
        with Image.open(self.difference) as image:
            self.assertIsNone(image.getbbox())

    def test_blank_wrong_color_and_shifted_layout_fail(self):
        wrong_color = self.expected.copy()
        ImageDraw.Draw(wrong_color).rectangle((20, 20, 80, 80), fill='#f6b44b')
        shifted = Image.new('RGB', (100, 100), '#15243a')
        ImageDraw.Draw(shifted).rectangle((30, 20, 90, 80), fill='#53d6bd')
        for actual in [Image.new('RGB', (100, 100), 'white'), wrong_color, shifted]:
            with self.subTest(actual=actual):
                result = compare(self.expected, actual, self.difference)
                self.assertFalse(result['passed'])
                with Image.open(self.difference) as image:
                    self.assertIsNotNone(image.getbbox())

    def test_small_channel_variation_is_tolerated(self):
        actual = self.expected.point(lambda value: min(255, value + 3))
        result = compare(self.expected, actual, self.difference)
        self.assertTrue(result['passed'])
        self.assertEqual(result['changed_pixels'], 0)

    def test_small_number_of_antialiasing_outliers_is_tolerated(self):
        actual = self.expected.copy()
        actual.putpixel((20, 20), (255, 255, 255))
        result = compare(self.expected, actual, self.difference)
        self.assertTrue(result['passed'])
        self.assertEqual(result['changed_pixels'], 1)

    def test_viewport_change_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'dimensions differ'):
            compare(self.expected, Image.new('RGB', (101, 100)), self.difference)


if __name__ == '__main__':
    unittest.main()
