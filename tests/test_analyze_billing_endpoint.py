import unittest
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from unittest.mock import patch
import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

try:
    import flask  # noqa: F401
    from flask import Flask
    FLASK_AVAILABLE = True
except Exception:  # pragma: no cover - if Flask missing
    FLASK_AVAILABLE = False
    server = None

if FLASK_AVAILABLE:
    import server

@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed")

class TestAnalyzeBillingEndpoint(unittest.TestCase):
    @patch('server.determine_applicable_pauschale_func')
    @patch('server.load_data', return_value=True)
    def test_analyze_billing_returns_evaluated(self, _, mock_determine):
        mock_determine.return_value = {
            "type": "Pauschale",
            "details": {"Pauschale": "X"},
            "bedingungs_pruef_html": "<p></p>",
            "bedingungs_fehler": [],
            "conditions_met": True,
            "evaluated_pauschalen": [
                {
                    "code": "X",
                    "details": {"Taxpunkte": "1"},
                    "is_valid_structured": True,
                    "bedingungs_pruef_html": "<p></p>",
                    "taxpunkte": 1.0,
                }
            ],
        }
        server.app.config['TESTING'] = True
        with server.app.test_client() as client:
            payload = {"inputText": "test", "icd": [], "gtin": []}
            response = client.post('/api/analyze-billing', json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn('evaluated_pauschalen', data)
            self.assertIsInstance(data['evaluated_pauschalen'], list)
            first = data['evaluated_pauschalen'][0]
            self.assertIn('code', first)
            self.assertIn('bedingungs_pruef_html', first)
            self.assertIn('taxpunkte', first)

if __name__ == '__main__':
    unittest.main()
