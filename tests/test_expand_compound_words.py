import unittest
import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from utils import expand_compound_words

class TestExpandCompoundWords(unittest.TestCase):
    def test_linksherzkatheter_expands(self):
        result = expand_compound_words("LinksHerzkatheter")
        self.assertIn("links Herzkatheter", result)
        self.assertIn("Herzkatheter", result)

    def test_untersuchung_unchanged(self):
        result = expand_compound_words("Untersuchung")
        self.assertEqual(result, "Untersuchung")

if __name__ == '__main__':
    unittest.main()
