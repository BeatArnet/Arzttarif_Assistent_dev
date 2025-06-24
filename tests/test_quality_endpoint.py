import unittest
from unittest.mock import patch
import server

class TestQualityEndpoint(unittest.TestCase):
    @patch('server.load_data', return_value=True)
    def test_quality_endpoint(self, _):
        app = server.create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            baseline = {"code": "TEST"}
            response = client.post('/api/quality', json={'baseline': baseline})
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn('result', data)
            self.assertIn('baseline', data)
            self.assertIn('match', data)
