import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app


class TranscriptionContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def assert_transcript(self, expected_text):
        with patch("main.transcribe_audio", new=AsyncMock(return_value=expected_text)):
            response = self.client.post(
                "/transcribe",
                files={"audio": ("recording.webm", b"test-audio", "audio/webm")},
                data={"language": "en"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["request_id"])
        self.assertEqual(payload["transcript"], {
            "text": expected_text,
            "language": "en",
            "confidence": None,
        })

    def test_simple_sentence(self):
        self.assert_transcript("Hello, this is a simple test.")

    def test_name_and_phone_sentence(self):
        self.assert_transcript(
            "My name is Rahul Sharma and my phone number is 9876543210."
        )

    def test_application_id_sentence(self):
        self.assert_transcript("My application ID is ABX 2047 891.")


if __name__ == "__main__":
    unittest.main()
