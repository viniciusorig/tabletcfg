import unittest

from tabletcfg.devices import parse_device_node, parse_pointer_devices, select_tablet

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

T505 = {"ID_INPUT_TABLET": "1", "ID_VENDOR_ID": "08f2", "ID_MODEL_ID": "6811",
        "NAME": '"SZ PING-IT INC.  T505 Graphic Tablet"'}
UDEV = [
    {**T505, "DEVNAME": "/dev/input/event24", "ID_INPUT_WIDTH_MM": "203", "ID_INPUT_HEIGHT_MM": "135"},
    {**T505, "DEVNAME": "/dev/input/event27", "ID_INPUT_WIDTH_MM": "204", "ID_INPUT_HEIGHT_MM": "136"},
    {**T505, "DEVNAME": "/dev/input/mouse3"},
    {"ID_INPUT_MOUSE": "1", "DEVNAME": "/dev/input/event3"},
]
# (xinput id, nome, nó)
POINTERS = [
    (11, "Logitech USB Optical Mouse", "/dev/input/event3"),
    (22, "SZ PING-IT INC.  T505 Graphic Tablet Mouse", "/dev/input/event23"),
    (23, "SZ PING-IT INC.  T505 Graphic Tablet Pen (0)", "/dev/input/event27"),
]


class DevicesTest(unittest.TestCase):
    def test_parse_pointer_devices_only_slaves(self):
        devs = parse_pointer_devices(XINPUT_LIST)
        self.assertEqual(devs, [
            (4, "Virtual core XTEST pointer"),
            (11, "Logitech USB Optical Mouse"),
            (22, "SZ PING-IT INC.  T505 Graphic Tablet Mouse"),
            (23, "SZ PING-IT INC.  T505 Graphic Tablet Pen (0)"),
        ])

    def test_parse_device_node(self):
        self.assertEqual(parse_device_node(PROPS), "/dev/input/event27")
        self.assertIsNone(parse_device_node("Device 'x':\n\tDevice Enabled (1):\t1\n"))

    def test_select_tablet_with_pen_present(self):
        t = select_tablet(UDEV, POINTERS)
        self.assertEqual((t.vendor, t.product), ("08f2", "6811"))
        self.assertEqual(t.nodes, ("/dev/input/event24", "/dev/input/event27"))
        self.assertEqual(t.xinput_ids, (23,))
        self.assertEqual(t.size_mm, (204.0, 136.0))  # tamanho do nó da caneta
        self.assertEqual(t.name, "SZ PING-IT INC.  T505 Graphic Tablet")

    def test_select_tablet_before_pen_first_proximity(self):
        # o X só cria o "Pen (0)" quando a caneta chega perto da mesa
        t = select_tablet(UDEV, POINTERS[:2])
        self.assertEqual(t.xinput_ids, ())
        self.assertEqual((t.vendor, t.product), ("08f2", "6811"))
        self.assertIsNotNone(t.size_mm)

    def test_all_pointers_on_tablet_nodes_get_matrix(self):
        eraser = (30, "SZ PING-IT INC.  T505 Graphic Tablet Eraser (0)", "/dev/input/event27")
        self.assertEqual(select_tablet(UDEV, POINTERS + [eraser]).xinput_ids, (23, 30))

    def test_no_tablet(self):
        self.assertIsNone(select_tablet(UDEV[3:], POINTERS))

    def test_pad_and_unknown_size_ignored(self):
        pad = {**T505, "ID_INPUT_TABLET_PAD": "1", "DEVNAME": "/dev/input/event9"}
        t = select_tablet([pad, {**T505, "DEVNAME": "/dev/input/event27"}], POINTERS)
        self.assertEqual(t.nodes, ("/dev/input/event27",))
        self.assertIsNone(t.size_mm)


if __name__ == "__main__":
    unittest.main()
