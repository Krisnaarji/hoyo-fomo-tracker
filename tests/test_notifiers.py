"""app.notifiers has no fastapi dependency (json + urllib, both stdlib).

IMPORTANT: every test here patches app.notifiers.get_env directly rather
than touching real environment variables or .env - this must never read
or depend on the real DISCORD_WEBHOOK_URL secret, and all network calls
are mocked (zero real HTTP requests are made by this file).
"""
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from app import notifiers


class SendDiscordWebhookTestCase(unittest.TestCase):
    def test_raises_when_webhook_url_not_configured(self):
        with patch("app.notifiers.get_env", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                notifiers.send_discord_webhook("test message")

        self.assertIn("not set", str(ctx.exception))

    def test_raises_when_webhook_url_is_empty_string(self):
        with patch("app.notifiers.get_env", return_value=""):
            with self.assertRaises(RuntimeError):
                notifiers.send_discord_webhook("test message")

    def _mock_response(self, status):
        response = MagicMock()
        response.status = status
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)
        return response

    def test_succeeds_on_200(self):
        with patch("app.notifiers.get_env", return_value="https://fake.example/webhook"):
            with patch("urllib.request.urlopen", return_value=self._mock_response(200)):
                notifiers.send_discord_webhook("hello")  # should not raise

    def test_succeeds_on_204(self):
        with patch("app.notifiers.get_env", return_value="https://fake.example/webhook"):
            with patch("urllib.request.urlopen", return_value=self._mock_response(204)):
                notifiers.send_discord_webhook("hello")  # should not raise

    def test_raises_on_unexpected_status(self):
        with patch("app.notifiers.get_env", return_value="https://fake.example/webhook"):
            with patch("urllib.request.urlopen", return_value=self._mock_response(500)):
                with self.assertRaises(RuntimeError) as ctx:
                    notifiers.send_discord_webhook("hello")

        self.assertIn("500", str(ctx.exception))

    def test_raises_clear_error_on_url_error(self):
        with patch("app.notifiers.get_env", return_value="https://fake.example/webhook"):
            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
                with self.assertRaises(RuntimeError) as ctx:
                    notifiers.send_discord_webhook("hello")

        self.assertIn("Failed to send Discord webhook", str(ctx.exception))

    def test_request_payload_has_expected_shape(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["content_type"] = request.get_header("Content-type")
            captured["body"] = request.data
            return self._mock_response(200)

        with patch("app.notifiers.get_env", return_value="https://fake.example/webhook"):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                notifiers.send_discord_webhook("hello world")

        import json
        self.assertEqual(captured["url"], "https://fake.example/webhook")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["content_type"], "application/json")
        body = json.loads(captured["body"])
        self.assertEqual(body["content"], "hello world")
        self.assertEqual(body["username"], "HoYo FOMO Tracker")


if __name__ == "__main__":
    unittest.main()
