import unittest

from tabletcfg.geometry import bbox, fit_view, point_in, rect_from_drag

REF = (0, 0, 100, 50)


class GeometryTest(unittest.TestCase):
    def assertRect(self, got, exp):
        for a, b in zip(got, exp):
            self.assertAlmostEqual(a, b)

    def test_drag_normal(self):
        self.assertRect(rect_from_drag((10, 10), (60, 35), REF), (0.1, 0.2, 0.5, 0.5))

    def test_drag_reversed(self):
        self.assertRect(rect_from_drag((60, 35), (10, 10), REF), (0.1, 0.2, 0.5, 0.5))

    def test_drag_beyond_edges_is_clamped(self):
        self.assertRect(rect_from_drag((-50, -50), (500, 500), REF), (0, 0, 1, 1))

    def test_drag_tiny_gets_min_size_and_stays_inside(self):
        x, y, w, h = rect_from_drag((99, 49), (100, 50), REF)
        self.assertAlmostEqual(w, 0.05)
        self.assertAlmostEqual(h, 0.05)
        self.assertLessEqual(x + w, 1 + 1e-9)
        self.assertLessEqual(y + h, 1 + 1e-9)

    def test_drag_with_offset_ref(self):
        self.assertRect(rect_from_drag((1920, 0), (3200, 720), (1920, 0, 2560, 1440)),
                        (0, 0, 0.5, 0.5))

    def test_fit_view_round_trip_and_centering(self):
        v = fit_view((0, 0, 4480, 1440), 472, 200, margin=12)
        self.assertAlmostEqual(v.scale, 448 / 4480)
        px, py = v.to_widget(4480, 1440)
        self.assertAlmostEqual(px, 460)
        x, y = v.to_world(*v.to_widget(1000, 700))
        self.assertAlmostEqual(x, 1000)
        self.assertAlmostEqual(y, 700)

    def test_bbox_and_point_in(self):
        self.assertEqual(bbox([(0, 0, 10, 10), (10, 5, 10, 10)]), (0, 0, 20, 15))
        self.assertTrue(point_in((0, 0, 10, 10), 10, 10))
        self.assertFalse(point_in((0, 0, 10, 10), 11, 5))


if __name__ == "__main__":
    unittest.main()
