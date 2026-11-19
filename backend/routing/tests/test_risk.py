from django.test import SimpleTestCase

from routing.services.risk import RiskLevel, classify_checkpoint

CALM = dict(wind_mph=0, rain_in_hr=0, snow_in_hr=0, load_lb=10_000)


class WindRulesTests(SimpleTestCase):
    def check(self, wind, expected, load=10_000):
        self.assertEqual(
            classify_checkpoint(wind, 0, 0, load), expected, f"wind={wind} load={load}"
        )

    def test_bands_are_lower_inclusive(self):
        self.check(24.9, RiskLevel.LOW)
        self.check(25, RiskLevel.MODERATE)
        self.check(34.9, RiskLevel.MODERATE)
        self.check(35, RiskLevel.HIGH)
        self.check(44.9, RiskLevel.HIGH)
        self.check(45, RiskLevel.SEVERE)
        self.check(54.9, RiskLevel.SEVERE)
        self.check(55, RiskLevel.NO_TRAVEL)

    def test_load_rule_no_travel_for_45_to_54_when_heavy(self):
        self.check(50, RiskLevel.NO_TRAVEL, load=30_001)
        self.check(50, RiskLevel.SEVERE, load=30_000)

    def test_load_rule_severe_for_35_to_44_when_very_heavy(self):
        self.check(40, RiskLevel.SEVERE, load=40_001)
        self.check(40, RiskLevel.HIGH, load=40_000)

    def test_no_travel_at_55_for_any_load(self):
        self.check(60, RiskLevel.NO_TRAVEL, load=1_000)


class RainAndSnowTests(SimpleTestCase):
    def test_rain_bands(self):
        def rain(v):
            return classify_checkpoint(0, v, 0, 10_000)

        self.assertEqual(rain(0.09), RiskLevel.LOW)
        self.assertEqual(rain(0.10), RiskLevel.MODERATE)
        self.assertEqual(rain(0.25), RiskLevel.HIGH)
        self.assertEqual(rain(0.50), RiskLevel.SEVERE)
        self.assertEqual(rain(1.00), RiskLevel.SEVERE)  # ">1.00" is No Travel
        self.assertEqual(rain(1.01), RiskLevel.NO_TRAVEL)

    def test_snow_bands(self):
        def snow(v):
            return classify_checkpoint(0, 0, v, 10_000)

        self.assertEqual(snow(0.4), RiskLevel.LOW)
        self.assertEqual(snow(0.5), RiskLevel.MODERATE)
        self.assertEqual(snow(1.0), RiskLevel.HIGH)
        self.assertEqual(snow(2.0), RiskLevel.SEVERE)
        self.assertEqual(snow(3.0), RiskLevel.SEVERE)  # ">3.0" is No Travel
        self.assertEqual(snow(3.1), RiskLevel.NO_TRAVEL)

    def test_overall_risk_is_worst_condition(self):
        self.assertEqual(classify_checkpoint(10, 0.3, 0, 10_000), RiskLevel.HIGH)
        self.assertEqual(classify_checkpoint(30, 0, 2.5, 10_000), RiskLevel.SEVERE)
