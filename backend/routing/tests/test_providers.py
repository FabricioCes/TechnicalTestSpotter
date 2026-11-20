from datetime import datetime, timezone
from unittest import mock

from django.test import SimpleTestCase

from routing.services import providers
from routing.services.providers import ProviderError, get_hourly_weather


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._payload


class RetryTests(SimpleTestCase):
    def test_retries_after_rate_limit_then_succeeds(self):
        responses = [FakeResponse(429), FakeResponse(200, {"ok": True})]
        with mock.patch.object(providers.requests, "get", side_effect=responses) as fake_get, mock.patch.object(
            providers.time, "sleep"
        ) as fake_sleep:
            data = providers._get_json("https://example.test/api", {}, attempts=3)
        self.assertEqual(data, {"ok": True})
        self.assertEqual(fake_get.call_count, 2)
        fake_sleep.assert_called_once()

    def test_rate_limit_error_is_readable_after_last_attempt(self):
        with mock.patch.object(providers.requests, "get", return_value=FakeResponse(429)), mock.patch.object(
            providers.time, "sleep"
        ):
            with self.assertRaisesMessage(ProviderError, "rate-limiting"):
                providers._get_json("https://example.test/api", {}, attempts=2)

    def test_does_not_retry_by_default(self):
        with mock.patch.object(providers.requests, "get", return_value=FakeResponse(503)) as fake_get:
            with self.assertRaises(ProviderError):
                providers._get_json("https://example.test/api", {})
        self.assertEqual(fake_get.call_count, 1)


class WeatherCacheTests(SimpleTestCase):
    PAYLOAD = {
        "hourly": {
            "time": ["2026-12-01T00:00"],
            "wind_speed_10m": [10.0],
            "rain": [0.0],
            "snowfall": [0.0],
        }
    }

    def setUp(self):
        providers._weather_cache.clear()
        self.start = datetime(2026, 12, 1, tzinfo=timezone.utc)

    def test_repeated_points_are_fetched_once(self):
        with mock.patch.object(providers, "_get_json", return_value=self.PAYLOAD) as fake:
            first = get_hourly_weather([(39.7392, -104.9903)], self.start, self.start)
            second = get_hourly_weather([(39.7391, -104.9904)], self.start, self.start)
        self.assertEqual(fake.call_count, 1)
        self.assertEqual(first, second)

    def test_duplicate_points_in_one_call_share_a_request_slot(self):
        payload = [self.PAYLOAD]
        with mock.patch.object(providers, "_get_json", return_value=payload) as fake:
            result = get_hourly_weather([(39.7392, -104.9903), (39.7391, -104.9904)], self.start, self.start)
        self.assertEqual(len(result), 2)
        self.assertEqual(fake.call_args.args[1]["latitude"], "39.74")
