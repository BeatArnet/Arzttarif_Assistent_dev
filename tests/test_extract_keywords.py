import unittest
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from utils import extract_keywords

class TestExtractKeywords(unittest.TestCase):
    def test_synonym_expansion_appendix(self):
        tokens = extract_keywords("Blinddarmentfernung als alleinige Leistung")
        self.assertIn("appendektomie", tokens)
        self.assertIn("appendix", tokens)

    def test_synonym_expansion_warze(self):
        tokens = extract_keywords("Entfernung Warze mit dem scharfen L\xf6ffel")
        self.assertIn("hyperkeratose", tokens)

if __name__ == '__main__':
    unittest.main()
