from datetime import datetime, timezone

from django.test import SimpleTestCase

from routing.services.recommendation import Checkpoint, rank_routes, summarize
from routing.services.risk import RiskLevel

T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def cp(miles, level):
    return Checkpoint(
        index=0, mile=miles, segment_miles=miles, lat=0, lon=0, eta=T,
        wind_mph=0, rain_in_hr=0, snow_in_hr=0, level=level,
    )


def route(route_id, levels_and_miles, duration):
    checkpoints = [cp(m, lvl) for m, lvl in levels_and_miles]
    total = sum(m for m, _ in levels_and_miles)
    return summarize(route_id, route_id, total, duration, checkpoints, [])


class SummaryTests(SimpleTestCase):
    def test_miles_are_attributed_per_level(self):
        r = route("a", [(10, RiskLevel.LOW), (20, RiskLevel.SEVERE), (5, RiskLevel.HIGH)], 100)
        self.assertEqual(r.severe_miles, 20)
        self.assertEqual(r.high_miles, 5)
        self.assertEqual(r.no_travel_miles, 0)
        self.assertAlmostEqual(r.average_risk, (0 * 10 + 3 * 20 + 2 * 5) / 35, places=2)


class RankingTests(SimpleTestCase):
    def test_fewest_severe_miles_wins_over_shorter_time(self):
        fast_but_severe = route("fast", [(50, RiskLevel.SEVERE)], 1000)
        slow_but_clear = route("slow", [(50, RiskLevel.LOW)], 5000)
        ranked = rank_routes([fast_but_severe, slow_but_clear])
        self.assertEqual(ranked[0].route_id, "slow")
        self.assertTrue(ranked[0].recommended)
        self.assertEqual(ranked[1].rank, 2)

    def test_high_miles_break_tie_on_severe(self):
        more_high = route("a", [(40, RiskLevel.HIGH)], 100)
        less_high = route("b", [(40, RiskLevel.MODERATE)], 900)
        self.assertEqual(rank_routes([more_high, less_high])[0].route_id, "b")

    def test_no_travel_is_avoided_first(self):
        blocked = route("blocked", [(1, RiskLevel.NO_TRAVEL), (99, RiskLevel.LOW)], 100)
        severe = route("severe", [(30, RiskLevel.SEVERE)], 900)
        self.assertEqual(rank_routes([blocked, severe])[0].route_id, "severe")

    def test_travel_time_breaks_full_tie(self):
        a = route("a", [(40, RiskLevel.LOW)], 3000)
        b = route("b", [(40, RiskLevel.LOW)], 2000)
        self.assertEqual(rank_routes([a, b])[0].route_id, "b")
