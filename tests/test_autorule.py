import unittest

from pathlib import Path
from unittest import mock

from tabletcfg.autorule import (
    install_rule, parse_rule_ids, render_rules, render_service, rule_line, rule_needs_update,
)
from tabletcfg.proc import CommandError


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
        # simple: o processo espera a caneta aparecer, sem o timeout de 90 s do oneshot
        self.assertIn("Type=simple", s)
        self.assertIn("ExecStart=/home/u/.local/bin/tabletcfg apply --saved --follow", s)

    def test_no_polkit_agent_gives_actionable_message(self):
        err = CommandError("'pkexec ...' falhou (127): Error executing command as another user: "
                           "No authentication agent found.")
        with mock.patch("tabletcfg.autorule.run", side_effect=err):
            with self.assertRaises(CommandError) as cm:
                install_rule("08f2", "6811", Path("/nao/existe.rules"))
        msg = str(cm.exception)
        self.assertIn("tabletcfg install-rule", msg)
        self.assertIn("polkit-gnome", msg)


if __name__ == "__main__":
    unittest.main()
