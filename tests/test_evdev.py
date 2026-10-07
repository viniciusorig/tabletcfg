import struct
import unittest

from tabletcfg.evdev import (
    EV_KEY, EV_SYN, EVIOCGRAB, EVENT_SIZE, FrameReader, UI_SET_KEYBIT, pack_event,
    uinput_user_dev, unpack_events,
)


class StructTest(unittest.TestCase):
    def test_event_round_trip(self):
        data = pack_event(EV_KEY, 29, 1) + pack_event(EV_SYN, 0, 0)
        self.assertEqual(len(data), 2 * EVENT_SIZE)
        self.assertEqual(unpack_events(data), [(EV_KEY, 29, 1), (EV_SYN, 0, 0)])

    def test_event_size_matches_64bit_kernel(self):
        self.assertEqual(EVENT_SIZE, 24)

    def test_ioctl_numbers(self):
        self.assertEqual(EVIOCGRAB, 0x40044590)
        self.assertEqual(UI_SET_KEYBIT, 0x40045565)

    def test_uinput_user_dev_layout(self):
        data = uinput_user_dev("tabletcfg", 0x08F2, 0x6811)
        self.assertEqual(len(data), 80 + 8 + 4 + 4 * 64 * 4)
        self.assertTrue(data.startswith(b"tabletcfg\0"))
        self.assertEqual(struct.unpack_from("HHHH", data, 80), (0x03, 0x08F2, 0x6811, 1))


class FrameReaderTest(unittest.TestCase):
    def test_groups_until_syn_report(self):
        r = FrameReader()
        self.assertEqual(r.feed([(4, 4, 1), (EV_KEY, 29, 1)]), [])
        frames = r.feed([(EV_KEY, 44, 1), (EV_SYN, 0, 0), (EV_KEY, 44, 0), (EV_SYN, 0, 0)])
        self.assertEqual(frames, [[(4, 4, 1), (EV_KEY, 29, 1), (EV_KEY, 44, 1)],
                                  [(EV_KEY, 44, 0)]])

    def test_syn_dropped_discards_partial_frame(self):
        r = FrameReader()
        r.feed([(EV_KEY, 29, 1), (EV_SYN, 3, 0)])  # SYN_DROPPED
        self.assertEqual(r.feed([(EV_KEY, 30, 1), (EV_SYN, 0, 0)]), [[(EV_KEY, 30, 1)]])


if __name__ == "__main__":
    unittest.main()
