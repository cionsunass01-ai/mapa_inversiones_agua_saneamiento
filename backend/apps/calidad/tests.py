from django.test import TestCase, Client
from unittest.mock import patch
from django.db.utils import OperationalError

class HealthCheckTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_ok(self):
        # By default the test database is available
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            str(response.content, encoding='utf8'),
            {"status": "ok", "database": "ok"}
        )

    @patch('config.urls.connection.cursor')
    def test_health_check_db_down(self, mock_cursor):
        # Simulate a database failure
        mock_cursor.side_effect = OperationalError("DB is down")
        
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            str(response.content, encoding='utf8'),
            {"status": "error", "database": "error"}
        )
