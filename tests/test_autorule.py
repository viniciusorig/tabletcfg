import unittest

from pathlib import Path
from unittest import mock

from tabletcfg.autorule import (
    WrongPassword, buttons_rule_line, ensure_auto_apply, install_rule, parse_rule_ids,
    render_buttons_service, render_rules, render_service, rule_line, rule_needs_update,
)
from tabletcfg.devices import Tablet
from tabletcfg.proc import CommandError

NOWHERE = Path("/nao/existe.rules")
TABLET = Tablet((23,), "T505", ("/dev/input/event27",), "08f2", "6811", (204.0, 136.0))


class AutoruleTest(unittest.TestCase):
    def test_rule_line(self):
        line = rule_line("08f2", "6811")
        self.assertIn('ATTRS{idVendor}=="08f2"', line)
        self.assertIn('ATTRS{idProduct}=="6811"', line)
        self.assertIn('ENV{ID_INPUT_TABLET}=="1"', line)
        self.assertIn('ENV{SYSTEMD_USER_WANTS}+="tabletcfg-apply.service"', line)
        self.assertIn('TAG+="systemd"', line)
        self.assertNotIn("\n", line)

    def test_buttons_rule_line_matches_key_nodes(self):
        line = buttons_rule_line("08f2", "6811")
        self.assertIn('ENV{ID_INPUT_KEY}=="1"', line)
        self.assertIn('ATTRS{idVendor}=="08f2"', line)
        self.assertIn('ENV{SYSTEMD_USER_WANTS}+="tabletcfg-buttons.service"', line)

    def test_rules_include_buttons_line(self):
        text = render_rules({("08f2", "6811")})
        self.assertIn(rule_line("08f2", "6811"), text)
        self.assertIn(buttons_rule_line("08f2", "6811"), text)

    def test_old_rule_without_buttons_needs_update(self):
        old = "# Gerado por tabletcfg — não editar à mão\n" + rule_line("08f2", "6811") + "\n"
        self.assertTrue(rule_needs_update(old, "08f2", "6811"))

    def test_buttons_service(self):
        s = render_buttons_service("/home/u/.local/bin/tabletcfg")
        self.assertIn("Type=simple", s)
        self.assertIn("ExecStart=/home/u/.local/bin/tabletcfg buttons --follow", s)

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

    def test_gui_password_goes_to_sudo_stdin_not_args(self):
        with mock.patch("tabletcfg.autorule.run") as run:
            install_rule("08f2", "6811", NOWHERE, password="segredo")
        args, kwargs = run.call_args
        cmd = args[0]
        self.assertEqual(cmd[:5], ["sudo", "-S", "-k", "-p", ""])
        self.assertNotIn("segredo", " ".join(cmd))
        self.assertEqual(kwargs["input"], "segredo\n")
        self.assertEqual(cmd[-1], str(NOWHERE))

    def test_terminal_path_uses_plain_sudo(self):
        with mock.patch("tabletcfg.autorule.run") as run:
            install_rule("08f2", "6811", NOWHERE)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[:3], ["sudo", "sh", "-c"])
        self.assertNotIn("pkexec", cmd)

    def test_wrong_password_is_recognized(self):
        err = CommandError("'sudo ...' falhou (1): sudo: no password was provided\n"
                           "sudo: 1 incorrect password attempt")
        with mock.patch("tabletcfg.autorule.run", side_effect=err):
            with self.assertRaises(WrongPassword):
                install_rule("08f2", "6811", NOWHERE, password="errada")


class EnsureAutoApplyTest(unittest.TestCase):
    def setUp(self):
        for name in ("install_service", "start_buttons_service"):
            p = mock.patch(f"tabletcfg.autorule.{name}")
            p.start()
            self.addCleanup(p.stop)

    def test_starts_buttons_service_when_tablet_connected(self):
        with mock.patch("tabletcfg.autorule._read", return_value=render_rules({("08f2", "6811")})):
            ensure_auto_apply(TABLET, None, NOWHERE)
        from tabletcfg import autorule
        autorule.start_buttons_service.assert_called_once()

    def test_retries_after_wrong_password(self):
        asked = []

        def ask(retry):
            asked.append(retry)
            return "senha"

        with mock.patch("tabletcfg.autorule.install_rule",
                        side_effect=[WrongPassword("Senha incorreta"), None]) as inst:
            warns = ensure_auto_apply(TABLET, ask, NOWHERE)
        self.assertEqual(warns, [])
        self.assertEqual(asked, [False, True])
        self.assertEqual(inst.call_count, 2)

    def test_gives_up_after_three_wrong_passwords(self):
        with mock.patch("tabletcfg.autorule.install_rule",
                        side_effect=WrongPassword("Senha incorreta")) as inst:
            warns = ensure_auto_apply(TABLET, lambda retry: "x", NOWHERE)
        self.assertEqual(inst.call_count, 3)
        self.assertTrue(any("incorreta" in w for w in warns))

    def test_cancel_skips_rule_with_warning(self):
        with mock.patch("tabletcfg.autorule.install_rule") as inst:
            warns = ensure_auto_apply(TABLET, lambda retry: None, NOWHERE)
        inst.assert_not_called()
        self.assertTrue(any("cancelad" in w for w in warns))

    def test_rule_already_present_does_not_ask(self):
        ask = mock.Mock()
        with mock.patch("tabletcfg.autorule._read", return_value=render_rules({("08f2", "6811")})):
            warns = ensure_auto_apply(TABLET, ask, NOWHERE)
        ask.assert_not_called()
        self.assertEqual(warns, [])


if __name__ == "__main__":
    unittest.main()
