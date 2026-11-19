from unittest import mock

from django.test import SimpleTestCase
from django.test import Client

from routing.services import providers
from routing.services.providers import Place, _photon_label, suggest_addresses

PHOTON_FEATURES = {
    "features": [
        {
            "properties": {
                "housenumber": "9",
                "street": "Hi River Road",
                "city": "Barnstable",
                "state": "Massachusetts",
                "postcode": "02648",
                "countrycode": "US",
            },
            "geometry": {"type": "Point", "coordinates": [-70.4199611, 41.6592785]},
        },
        {
            # Non-US result must be dropped.
            "properties": {"street": "Hi River Road", "city": "Lima", "countrycode": "PE"},
            "geometry": {"type": "Point", "coordinates": [-77.0, -12.0]},
        },
    ]
}


class PhotonLabelTests(SimpleTestCase):
    def test_label_is_street_city_state_zip(self):
        label = _photon_label(PHOTON_FEATURES["features"][0]["properties"])
        self.assertEqual(label, "9 Hi River Road, Barnstable, Massachusetts 02648")

    def test_missing_city_falls_back_to_county(self):
        label = _photon_label({"street": "Main St", "county": "Kern", "state": "California"})
        self.assertEqual(label, "Main St, Kern, California")


class SuggestionTests(SimpleTestCase):
    def setUp(self):
        suggest_addresses.cache_clear()

    def test_keeps_only_us_results_with_coordinates(self):
        with mock.patch.object(providers, "_get_json", return_value=PHOTON_FEATURES):
            places = suggest_addresses("9 Hi River Road")
        self.assertEqual(len(places), 1)
        self.assertEqual(places[0].label, "9 Hi River Road, Barnstable, Massachusetts 02648")
        self.assertAlmostEqual(places[0].lat, 41.6592785)
        self.assertAlmostEqual(places[0].lon, -70.4199611)


class SuggestEndpointTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_short_query_returns_no_suggestions_without_calling_api(self):
        with mock.patch("routing.views.suggest_addresses") as fake:
            response = self.client.get("/api/addresses/suggest/", {"q": "9 "})
        self.assertEqual(response.json(), {"suggestions": []})
        fake.assert_not_called()

    def test_returns_suggestions_as_json(self):
        place = Place(label="9 Hi River Road, Barnstable, Massachusetts 02648", lat=41.6, lon=-70.4)
        with mock.patch("routing.views.suggest_addresses", return_value=(place,)):
            response = self.client.get("/api/addresses/suggest/", {"q": "9 Hi River Road"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["suggestions"][0]["lat"], 41.6)


class PlanInputTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()
        self.payload = {
            "origin": {"label": "9 Hi River Road", "lat": 41.6592785, "lon": -70.4199611},
            "destination": "Salt Lake City, Utah",
            "departure": "2026-12-01T08:00:00Z",
            "load_lb": 35000,
        }

    def test_suggestion_object_is_passed_as_place(self):
        with mock.patch("routing.views.plan_trip", return_value={"ok": True}) as fake:
            response = self.client.post("/api/plan/", self.payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        origin_arg = fake.call_args.args[0]
        self.assertIsInstance(origin_arg, Place)
        self.assertEqual(origin_arg.lat, 41.6592785)
        self.assertEqual(fake.call_args.args[1], "Salt Lake City, Utah")

    def test_invalid_coordinates_are_rejected(self):
        self.payload["origin"] = {"label": "x", "lat": 120, "lon": 0}
        response = self.client.post("/api/plan/", self.payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)
