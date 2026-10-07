import tempfile
import unittest
from pathlib import Path

from tabletcfg.buttons import (
    BUILTIN, Action, ButtonError, ButtonMap, action_label, format_action, load_maps,
    map_for, parse_action, save_maps,
)

T505 = BUILTIN["08f2:6811"]


class ActionTest(unittest.TestCase):
    def test_parse_each_kind(self):
        self.assertEqual(parse_action("key ctrl+z"), Action("key", (29, 44)))
        self.assertEqual(parse_action("click right"), Action("click", "right"))
        self.assertEqual(parse_action("scroll up"), Action("scroll", "up"))
        self.assertEqual(parse_action("command tabletcfg next"),
                         Action("command", "tabletcfg next"))
        self.assertEqual(parse_action("disable"), Action("disable", None))

    def test_command_keeps_spacing(self):
        self.assertEqual(parse_action("command  notify-send 'a  b'").arg, "notify-send 'a  b'")

    def test_round_trip(self):
        for text in ("key ctrl+shift+s", "click middle", "scroll left", "command krita",
                     "disable", "key ctrl"):
            self.assertEqual(format_action(parse_action(text)), text)

    def test_invalid(self):
        for text in ("", "key", "key ctrl+xyz", "click meio", "scroll", "command",
                     "command   ", "voar alto", "disable agora", 3, None):
            with self.subTest(text=text), self.assertRaises(ButtonError):
                parse_action(text)
    def test_label(self):
        self.assertEqual(action_label(parse_action("key ctrl+z")), "Atalho Ctrl+Z")
        self.assertEqual(action_label(parse_action("click right")), "Clique direito")
        self.assertEqual(action_label(parse_action("scroll down")), "Rolar para baixo")
        self.assertEqual(action_label(parse_action("command krita")), "Comando: krita")
        self.assertEqual(action_label(parse_action("disable")), "Desativado")



class ButtonMapTest(unittest.TestCase):
    def test_t505_builtin(self):
        self.assertEqual(len(T505.tablet), 8)
        self.assertEqual(len(T505.pen), 2)
        self.assertEqual(T505.ids(), [f"tablet{i}" for i in range(1, 9)] + ["pen1", "pen2"])
        self.assertEqual(T505.lookup(frozenset({29, 74})), "tablet1")
        self.assertEqual(T505.lookup(frozenset({29})), "tablet7")
        self.assertEqual(T505.lookup(frozenset({29, 21})), "pen1")  # Ctrl+Y, perto da ponta
        self.assertIsNone(T505.lookup(frozenset({30})))

    def test_signature_and_label(self):
        self.assertEqual(T505.signature("tablet3"), frozenset({26}))
        self.assertIsNone(T505.signature("tablet9"))
        self.assertEqual(ButtonMap.label("tablet3"), "Mesa 3")
        self.assertEqual(ButtonMap.label("pen2"), "Caneta 2")


class DevicesFileTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "devices.toml"

    def test_missing_file_uses_builtin(self):
        self.assertEqual(map_for("08f2", "6811", self.path), T505)
        self.assertIsNone(map_for("1234", "abcd", self.path))

    def test_round_trip_and_override(self):
        learned = ButtonMap((frozenset({30}), frozenset({29, 31})), ())
        save_maps({"1234:abcd": learned, "08f2:6811": ButtonMap((frozenset({2}),), ())}, self.path)
        self.assertEqual(load_maps(self.path)["1234:abcd"], learned)
        self.assertEqual(map_for("1234", "ABCD", self.path), learned)
        self.assertEqual(map_for("08f2", "6811", self.path).tablet, (frozenset({2}),))

    def test_invalid_file(self):
        self.path.write_text('["1234:abcd"]\ntablet = [["tecla-x"]]\n')
        with self.assertRaises(ButtonError) as cm:
            load_maps(self.path)
        self.assertIn("1234:abcd", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
