import unittest

from tabletcfg.matrix import (
    IDENTITY, build_ctm, compute_ctm, fit_tablet_area, transform,
)

DESKTOP = (4480, 1440)
DP2 = (0, 0, 1920, 1080)
DP4 = (1920, 0, 2560, 1440)
FULL = (0.0, 0.0, 1.0, 1.0)
MM = (204.0, 136.0)


class MatrixTest(unittest.TestCase):
    def assertPoint(self, m, src, expected):
        got = transform(m, *src)
        self.assertAlmostEqual(got[0], expected[0], places=6)
        self.assertAlmostEqual(got[1], expected[1], places=6)

    def test_identity_for_full_desktop(self):
        m = build_ctm(DESKTOP, (0, 0, 4480, 1440), FULL, 0)
        for a, b in zip(m, IDENTITY):
            self.assertAlmostEqual(a, b)

    def test_rotation_90_matches_known_matrix(self):
        m = build_ctm(DESKTOP, (0, 0, 4480, 1440), FULL, 90)
        self.assertEqual([round(v, 6) for v in m], [0, -1, 1, 1, 0, 0, 0, 0, 1])

    def test_rotations_map_tablet_top_left(self):
        # canto superior-esquerdo nativo da mesa vai para o canto girado no sentido horário
        expected = {0: (0, 0), 90: (1, 0), 180: (1, 1), 270: (0, 1)}
        for rot, corner in expected.items():
            with self.subTest(rot=rot):
                m = build_ctm((100, 100), (0, 0, 100, 100), FULL, rot)
                self.assertPoint(m, (0, 0), corner)

    def test_right_monitor_offset(self):
        m = compute_ctm(DESKTOP, DP4, FULL, FULL, 0, False, MM)
        self.assertPoint(m, (0, 0), (1920 / 4480, 0))
        self.assertPoint(m, (1, 1), (1, 1))

    def test_partial_screen_area(self):
        m = compute_ctm(DESKTOP, DP2, (0.5, 0.5, 0.5, 0.5), FULL, 0, False, MM)
        self.assertPoint(m, (0, 0), (960 / 4480, 540 / 1440))
        self.assertPoint(m, (1, 1), (1920 / 4480, 1080 / 1440))

    def test_tablet_crop(self):
        m = compute_ctm(DESKTOP, (0, 0, 4480, 1440), FULL, (0.25, 0.25, 0.5, 0.5), 0, False, MM)
        self.assertPoint(m, (0.25, 0.25), (0, 0))
        self.assertPoint(m, (0.75, 0.75), (1, 1))

    def test_fit_shrinks_height_for_wide_screen(self):
        # mesa 3:2 (1.5) num alvo 16:9 (1.777...) → reduz a altura e centraliza
        x, y, w, h = fit_tablet_area(FULL, 0, 2560 / 1440, MM)
        self.assertAlmostEqual(w, 1.0)
        self.assertAlmostEqual(h, 0.84375)
        self.assertAlmostEqual(y, 0.078125)
        self.assertAlmostEqual(x, 0.0)

    def test_fit_shrinks_width_for_tall_screen(self):
        x, y, w, h = fit_tablet_area(FULL, 0, 1.0, MM)
        self.assertAlmostEqual(h, 1.0)
        self.assertAlmostEqual(w, 136 / 204)
        self.assertAlmostEqual(x, (1 - 136 / 204) / 2)

    def test_fit_with_rotation_90(self):
        # girada, a altura da mesa vira largura na tela: alvo 16:9 → reduz a largura nativa
        x, y, w, h = fit_tablet_area(FULL, 90, 2560 / 1440, MM)
        self.assertAlmostEqual(h, 1.0)
        self.assertAlmostEqual(w, 0.375)
        self.assertAlmostEqual(x, 0.3125)

    def test_fit_inside_partial_area_stays_inside(self):
        area = (0.5, 0.5, 0.5, 0.5)
        x, y, w, h = fit_tablet_area(area, 0, 2560 / 1440, MM)
        self.assertGreaterEqual(y, 0.5)
        self.assertLessEqual(y + h, 1.0 + 1e-9)
        self.assertAlmostEqual(w, 0.5)

    def test_compute_keep_aspect_preserves_circles(self):
        m = compute_ctm(DESKTOP, DP4, FULL, FULL, 0, True, MM)
        # um quadrado de 10mm na mesa deve virar um quadrado em pixels
        x0, y0 = transform(m, 0.5, 0.5)
        x1, y1 = transform(m, 0.5 + 10 / 204, 0.5 + 10 / 136)
        self.assertAlmostEqual((x1 - x0) * 4480, (y1 - y0) * 1440, places=3)

    def test_invalid_rotation(self):
        with self.assertRaises(ValueError):
            build_ctm(DESKTOP, DP2, FULL, 45)


if __name__ == "__main__":
    unittest.main()
