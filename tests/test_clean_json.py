import json
import tempfile
import unittest
from pathlib import Path

from clean_json import clean_file


class CleanJsonTests(unittest.TestCase):
    def test_clean_file_removes_control_chars(self):
        sample = '{"a": "b\x0c"}'
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "test.json"
            src.write_bytes(sample.encode("utf-8", "surrogateescape"))
            cleaned_path = clean_file(src)
            self.assertTrue(cleaned_path.exists())
            data = json.loads(cleaned_path.read_text(encoding="utf-8"))
            self.assertEqual(data, {"a": "b"})


if __name__ == "__main__":
    unittest.main()
