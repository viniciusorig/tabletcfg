import unittest

from tabletcfg.keys import (
    ComboError, MODIFIERS, code_of, combo_label, format_combo, name_of, parse_combo,
)


class NamesTest(unittest.TestCase):
    def test_round_trip_known_names(self):
        for name in ("a", "z", "1", "0", "f1", "f12", "tab", "space", "enter", "esc",
                     "kp_add", "kp_subtract", "bracketleft", "leftctrl", "delete"):
            self.assertEqual(name_of(code_of(name)), name)

    def test_evdev_codes(self):
        self.assertEqual(code_of("leftctrl"), 29)
        self.assertEqual(code_of("z"), 44)
        self.assertEqual(code_of("kp_subtract"), 74)
        self.assertEqual(code_of("bracketleft"), 26)

    def test_aliases(self):
        self.assertEqual(code_of("ctrl"), 29)
        self.assertEqual(code_of("["), 26)
        self.assertEqual(code_of("KP_Add"), 78)

    def test_unknown_code_has_generic_name(self):
        self.assertEqual(name_of(0x130), "code304")
        self.assertEqual(code_of("code304"), 0x130)

    def test_unknown_name(self):
        with self.assertRaises(ComboError):
            code_of("tecla-que-nao-existe")


class ComboTest(unittest.TestCase):
    def test_parse_orders_modifiers_first(self):
        self.assertEqual(parse_combo("z+ctrl+shift"), (29, 42, 44))

    def test_modifier_only(self):
        self.assertEqual(parse_combo("ctrl"), (29,))
        self.assertEqual(parse_combo("ctrl+alt"), (29, 56))

    def test_format_is_canonical(self):
        self.assertEqual(format_combo((44, 29, 42)), "ctrl+shift+z")
        self.assertEqual(format_combo((29,)), "ctrl")

    def test_round_trip(self):
        for text in ("ctrl+z", "ctrl+shift+s", "alt+f4", "super", "kp_add", "ctrl+bracketleft"):
            self.assertEqual(format_combo(parse_combo(text)), text)

    def test_invalid(self):
        for text in ("", "ctrl+", "a+b", "ctrl+xyz", "+"):
            with self.subTest(text=text), self.assertRaises(ComboError):
                parse_combo(text)

    def test_label(self):
        self.assertEqual(combo_label((29, 42, 31)), "Ctrl+Shift+S")
        self.assertEqual(combo_label((29, 74)), "Ctrl+KP −")
        self.assertEqual(combo_label((26,)), "[")
        self.assertEqual(combo_label((57,)), "Espaço")

    def test_modifiers_set(self):
        self.assertIn(29, MODIFIERS)
        self.assertNotIn(44, MODIFIERS)


if __name__ == "__main__":
    unittest.main()
