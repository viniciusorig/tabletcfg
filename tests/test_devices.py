import unittest

from tabletcfg.devices import (
    order_candidates, parse_device_node, parse_pointer_devices, tablet_from_udev,
)

XINPUT_LIST = """\
⎡ Virtual core pointer                    \tid=2\t[master pointer  (3)]
⎜   ↳ Virtual core XTEST pointer              \tid=4\t[slave  pointer  (2)]
⎜   ↳ Logitech USB Optical Mouse              \tid=11\t[slave  pointer  (2)]
⎜   ↳ SZ PING-IT INC.  T505 Graphic Tablet Mouse\tid=22\t[slave  pointer  (2)]
⎜   ↳ SZ PING-IT INC.  T505 Graphic Tablet Pen (0)\tid=23\t[slave  pointer  (2)]
⎣ Virtual core keyboard                   \tid=3\t[master keyboard (2)]
    ↳ SZ PING-IT INC.  T505 Graphic Tablet    \tid=20\t[slave  keyboard (3)]
"""

PROPS = """\
Device 'SZ PING-IT INC.  T505 Graphic Tablet Pen (0)':
\tDevice Enabled (144):\t1
\tCoordinate Transformation Matrix (146):\t1.000000, 0.000000, 0.000000, 0.000000, 1.000000, 0.000000, 0.000000, 0.000000, 1.000000
\tDevice Node (265):\t"/dev/input/event27"
"""


class DevicesTest(unittest.TestCase):
    def test_parse_pointer_devices_only_slaves(self):
        devs = parse_pointer_devices(XINPUT_LIST)
        self.assertEqual(devs, [
            (4, "Virtual core XTEST pointer"),
            (11, "Logitech USB Optical Mouse"),
            (22, "SZ PING-IT INC.  T505 Graphic Tablet Mouse"),
            (23, "SZ PING-IT INC.  T505 Graphic Tablet Pen (0)"),
        ])

    def test_pen_first_and_xtest_dropped(self):
        ordered = order_candidates(parse_pointer_devices(XINPUT_LIST))
        self.assertEqual(ordered[0][0], 23)
        self.assertNotIn(4, [i for i, _ in ordered])

    def test_parse_device_node(self):
        self.assertEqual(parse_device_node(PROPS), "/dev/input/event27")
        self.assertIsNone(parse_device_node("Device 'x':\n\tDevice Enabled (1):\t1\n"))

    def test_tablet_from_udev(self):
        t = tablet_from_udev(23, "Pen", "/dev/input/event27", {
            "ID_INPUT_TABLET": "1", "ID_VENDOR_ID": "08f2", "ID_MODEL_ID": "6811",
            "ID_INPUT_WIDTH_MM": "204", "ID_INPUT_HEIGHT_MM": "136",
        })
        self.assertEqual((t.vendor, t.product, t.size_mm), ("08f2", "6811", (204.0, 136.0)))

    def test_tablet_without_size(self):
        t = tablet_from_udev(23, "Pen", "/dev/input/event27", {"ID_INPUT_TABLET": "1"})
        self.assertIsNone(t.size_mm)

    def test_not_a_tablet_or_pad(self):
        self.assertIsNone(tablet_from_udev(11, "Mouse", "/dev/input/event3", {"ID_INPUT_MOUSE": "1"}))
        self.assertIsNone(tablet_from_udev(30, "Pad", "/dev/input/event9",
                                           {"ID_INPUT_TABLET": "1", "ID_INPUT_TABLET_PAD": "1"}))


if __name__ == "__main__":
    unittest.main()
