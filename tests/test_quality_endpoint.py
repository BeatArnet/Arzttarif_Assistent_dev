import unittest
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from unittest.mock import patch
import server

class TestQualityEndpoint(unittest.TestCase):
    @patch('server.load_data', return_value=True)
    def test_quality_endpoint(self, _):
        server.app.config['TESTING'] = True
        with server.app.test_client() as client:
            baseline = {"code": "TEST"}
            response = client.post('/api/quality', json={'baseline': baseline})
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn('result', data)
            self.assertIn('baseline', data)
            self.assertIn('match', data)
