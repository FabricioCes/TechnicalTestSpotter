from django.test import SimpleTestCase

from routing.services.planner import MAX_CHECKPOINTS_PER_ROUTE, effective_interval


class EffectiveIntervalTests(SimpleTestCase):
    def test_short_route_keeps_requested_interval(self):
        self.assertEqual(effective_interval(500, 10), 10)

    def test_long_route_widens_interval_to_cap_checkpoints(self):
        interval = effective_interval(2600, 10)
        self.assertGreater(interval, 10)
        self.assertLessEqual(2600 / interval, MAX_CHECKPOINTS_PER_ROUTE)

    def test_never_goes_below_requested_interval(self):
        self.assertEqual(effective_interval(100, 50), 50)
