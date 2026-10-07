import unittest

from tabletcfg.buttons import Action, ButtonError, action_label, format_action, parse_action


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


if __name__ == "__main__":
    unittest.main()
