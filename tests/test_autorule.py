import unittest

from tabletcfg.autorule import (
    parse_rule_ids, render_rules, render_service, rule_line, rule_needs_update,
)


class AutoruleTest(unittest.TestCase):
    def test_rule_line(self):
        line = rule_line("08f2", "6811")
        self.assertIn('ATTRS{idVendor}=="08f2"', line)
        self.assertIn('ATTRS{idProduct}=="6811"', line)
        self.assertIn('ENV{ID_INPUT_TABLET}=="1"', line)
        self.assertIn('ENV{SYSTEMD_USER_WANTS}+="tabletcfg-apply.service"', line)
        self.assertIn('TAG+="systemd"', line)
        self.assertNotIn("\n", line)

    def test_render_and_parse_round_trip(self):
        ids = {("08f2", "6811"), ("256c", "006d")}
        text = render_rules(ids)
        self.assertTrue(text.startswith("# Gerado por tabletcfg"))
        self.assertEqual(parse_rule_ids(text), ids)

    def test_needs_update(self):
        text = render_rules({("08f2", "6811")})
        self.assertFalse(rule_needs_update(text, "08f2", "6811"))
        self.assertTrue(rule_needs_update(text, "256c", "006d"))
        self.assertTrue(rule_needs_update(None, "08f2", "6811"))

    def test_service(self):
        s = render_service("/home/u/.local/bin/tabletcfg")
        self.assertIn("Type=oneshot", s)
        self.assertIn("ExecStart=/home/u/.local/bin/tabletcfg apply --saved --wait 20", s)


if __name__ == "__main__":
    unittest.main()
