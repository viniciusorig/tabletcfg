import unittest

from tabletcfg.pressure import (
    LINEAR, PressureError, bezier_points, curve_for_firmness, drag_point, firmness_of,
    from_prop, parse_firmness, preset_label, to_prop, validate_curve,
)


def close(test, a, b):
    test.assertEqual(len(a), len(b))
    for x, y in zip(a, b):
        test.assertAlmostEqual(x, y, places=6)


class FirmnessTest(unittest.TestCase):
    def test_zero_is_linear(self):
        self.assertEqual(curve_for_firmness(0), LINEAR)

    def test_firm_curve_sits_below_diagonal(self):
        close(self, curve_for_firmness(1), (0.8, 0.0, 1.0, 0.2))
        close(self, curve_for_firmness(0.5), (0.4, 0.0, 1.0, 0.6))

    def test_soft_curve_sits_above_diagonal(self):
        close(self, curve_for_firmness(-1), (0.0, 0.8, 0.2, 1.0))

    def test_firmness_is_clamped(self):
        self.assertEqual(curve_for_firmness(3), curve_for_firmness(1))

    def test_round_trip(self):
        for s in (-1, -0.7, -0.5, 0, 0.25, 0.5, 1):
            self.assertAlmostEqual(firmness_of(curve_for_firmness(s)), s, places=6)

    def test_custom_curve_has_no_firmness(self):
        self.assertIsNone(firmness_of((0.3, 0.1, 0.6, 0.9)))


class LabelTest(unittest.TestCase):
    def test_nearest_preset(self):
        self.assertEqual(preset_label(LINEAR), "Normal")
        self.assertEqual(preset_label(curve_for_firmness(0.6)), "Firme")
        self.assertEqual(preset_label(curve_for_firmness(-0.9)), "Muito macia")

    def test_custom(self):
        self.assertEqual(preset_label((0.3, 0.1, 0.6, 0.9)), "Personalizada")


class ParseTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(parse_firmness("firme"), 0.5)
        self.assertEqual(parse_firmness("muito-macia"), -1.0)
        self.assertEqual(parse_firmness("Normal"), 0.0)

    def test_numbers(self):
        self.assertEqual(parse_firmness("40"), 0.4)
        self.assertEqual(parse_firmness("-100"), -1.0)

    def test_invalid(self):
        for text in ("101", "duro", "nan", ""):
            with self.assertRaises(PressureError):
                parse_firmness(text)


class ValidateTest(unittest.TestCase):
    def test_accepts_and_normalizes(self):
        self.assertEqual(validate_curve([0, 1, 1, 1]), (0.0, 1.0, 1.0, 1.0))

    def test_rejects(self):
        for bad in ([0, 0, 1], [0, 0, 1, 1.5], [0.8, 0, 0.2, 1], [0, 0, float("inf"), 1],
                    [True, 0, 1, 1], "abcd", None):
            with self.assertRaises(PressureError):
                validate_curve(bad)


class DragTest(unittest.TestCase):
    def test_clamps_to_unit_square(self):
        self.assertEqual(drag_point((0.2, 0.2, 0.8, 0.8), 0, -0.5, 1.4), (0.0, 1.0, 0.8, 0.8))

    def test_first_x_cannot_pass_second(self):
        self.assertEqual(drag_point((0.2, 0.2, 0.5, 0.8), 0, 0.9, 0.3), (0.5, 0.3, 0.5, 0.8))

    def test_second_x_cannot_pass_first(self):
        self.assertEqual(drag_point((0.4, 0.2, 0.8, 0.8), 1, 0.1, 0.5), (0.4, 0.2, 0.4, 0.5))


class PropTest(unittest.TestCase):
    def test_to_prop(self):
        self.assertEqual(to_prop((0.4, 0.0, 1.0, 0.6)), [0, 0, 0.4, 0.0, 1.0, 0.6, 1, 1])

    def test_from_prop(self):
        self.assertEqual(from_prop([0, 0, 0.4, 0, 1, 0.6, 1, 1]), (0.4, 0.0, 1.0, 0.6))
        self.assertIsNone(from_prop([0, 0, 1]))


class BezierTest(unittest.TestCase):
    def test_endpoints_and_linear(self):
        pts = bezier_points(LINEAR, 4)
        self.assertEqual(pts[0], (0.0, 0.0))
        self.assertEqual(pts[-1], (1.0, 1.0))
        for x, y in pts:
            self.assertAlmostEqual(x, y)


if __name__ == "__main__":
    unittest.main()
