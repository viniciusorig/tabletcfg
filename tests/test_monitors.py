import unittest

from tabletcfg.monitors import (
    Layout, Monitor, edid_identity, find_monitor, parse_xrandr, resolve_target,
)

EDID_DP2 = """\
\t\t00ffffffffffff00216d002401000000
\t\t26200104a5351e7829ee91a3544c9926
\t\t0f505421080031404540614081c08180
\t\t9500b300a9c0023a801871382d40582c
\t\t4500122c2100001e000000fd0030b4ca
\t\tca2e010a202020202020000000ff0030
\t\t303030303030303030303031000000fc
\t\t0053465032343135204648440a2001ac
"""
EDID_DP4 = """\
\t\t00ffffffffffff004d678327b5690f00
\t\t2f230104b53c21783f9eacaf4e3aad26
\t\t095055244b80d1c0b300950081808140
\t\t81c001010101565e00a0a0a029503020
\t\t350055502100001e000000ff00303030
\t\t30303030303030303030000000fd0041
\t\tc8fafa5a010a202020202020000000fc
\t\t0053464354465732373230300a200296
"""

XRANDR = (
    "Screen 0: minimum 8 x 8, current 4480 x 1440, maximum 32767 x 32767\n"
    "DP-0 disconnected (normal left inverted right x axis y axis)\n"
    "\tCTM: \t1.000000 0.000000 0.000000\n"
    "\t\t0.000000 1.000000 0.000000\n"
    "DP-4 connected primary 2560x1440+1920+0 (normal left inverted right x axis y axis) 600mm x 330mm\n"
    "\tEDID: \n" + EDID_DP4 +
    "\tBorderDimensions: 4 \n"
    "\t\tsupported: 4\n"
    "DP-2 connected 1920x1080+0+0 (normal left inverted right x axis y axis) 530mm x 300mm\n"
    "\tEDID: \n" + EDID_DP2 +
    "\tnon-desktop: 0 \n"
    "\t\tsupported: 0, 1\n"
    "HDMI-0 connected (normal left inverted right x axis y axis)\n"
    "\tnon-desktop: 0 \n"
)


class MonitorsTest(unittest.TestCase):
    def test_parse_layout_sorted_left_to_right(self):
        layout = parse_xrandr(XRANDR)
        self.assertEqual((layout.width, layout.height), (4480, 1440))
        self.assertEqual([m.name for m in layout.monitors], ["DP-2", "DP-4"])
        dp2, dp4 = layout.monitors
        self.assertEqual(dp2.rect, (0, 0, 1920, 1080))
        self.assertEqual(dp4.rect, (1920, 0, 2560, 1440))
        self.assertTrue(dp4.primary)
        self.assertFalse(dp2.primary)

    def test_edid_identities(self):
        dp2, dp4 = parse_xrandr(XRANDR).monitors
        self.assertEqual(dp2.id, "HKM-2400-00000001")
        self.assertEqual(dp4.id, "SKG-2783-000F69B5")

    def test_connected_but_disabled_output_is_skipped(self):
        names = [m.name for m in parse_xrandr(XRANDR).monitors]
        self.assertNotIn("HDMI-0", names)

    def test_no_edid_uses_connector_name(self):
        text = ("Screen 0: minimum 8 x 8, current 800 x 600, maximum 8 x 8\n"
                "VGA-1 connected 800x600+0+0 (normal) 0mm x 0mm\n")
        (m,) = parse_xrandr(text).monitors
        self.assertEqual(m.id, "VGA-1")

    def test_edid_identity_rejects_garbage(self):
        self.assertIsNone(edid_identity(b"\x00" * 128))
        self.assertIsNone(edid_identity(b""))

    def test_resolve_by_id_after_port_swap(self):
        layout = parse_xrandr(XRANDR)
        rect, warn = resolve_target(layout, "monitor", "SKG-2783-000F69B5", "DP-0")
        self.assertEqual(rect, (1920, 0, 2560, 1440))
        self.assertIsNone(warn)

    def test_resolve_falls_back_to_name(self):
        layout = parse_xrandr(XRANDR)
        rect, warn = resolve_target(layout, "monitor", "XXX-0000-0", "DP-2")
        self.assertEqual(rect, (0, 0, 1920, 1080))
        self.assertIsNone(warn)

    def test_resolve_missing_uses_desktop_and_warns(self):
        layout = parse_xrandr(XRANDR)
        rect, warn = resolve_target(layout, "monitor", "XXX-0000-0", "HDMI-9")
        self.assertEqual(rect, (0, 0, 4480, 1440))
        self.assertIn("HDMI-9", warn)

    def test_resolve_all(self):
        layout = parse_xrandr(XRANDR)
        self.assertEqual(resolve_target(layout, "all", "", "")[0], (0, 0, 4480, 1440))

    def test_identical_monitors_prefer_id_and_name(self):
        same = "AAA-0001-00000001"
        layout = Layout(3840, 1080, (
            Monitor("DP-1", same, 0, 0, 1920, 1080, True),
            Monitor("DP-3", same, 1920, 0, 1920, 1080, False),
        ))
        self.assertEqual(find_monitor(layout, same, "DP-3"), 1)
        self.assertEqual(find_monitor(layout, same, "DP-1"), 0)


if __name__ == "__main__":
    unittest.main()
