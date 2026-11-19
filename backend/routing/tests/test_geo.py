from django.test import SimpleTestCase

from routing.services.geo import checkpoint_miles, cumulative_miles, haversine_miles, sample_along


class GeoTests(SimpleTestCase):
    def test_haversine_one_degree_latitude_is_about_69_miles(self):
        self.assertAlmostEqual(haversine_miles(0, 0, 1, 0), 69.1, delta=0.2)

    def test_checkpoints_every_10_miles_include_both_ends(self):
        self.assertEqual(checkpoint_miles(25, 10), [0, 10, 20, 25])
        self.assertEqual(checkpoint_miles(20, 10), [0, 10, 20])

    def test_sample_along_interpolates(self):
        line = [(0.0, 0.0), (0.0, 1.0)]
        cum = cumulative_miles(line)
        lat, lon = sample_along(line, cum, cum[-1] / 2)
        self.assertAlmostEqual(lat, 0.0)
        self.assertAlmostEqual(lon, 0.5, places=3)
