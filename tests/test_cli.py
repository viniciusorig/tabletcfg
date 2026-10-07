import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tabletcfg import profiles
from tabletcfg.apply import PenNotReady
from tabletcfg.cli import active_profile, describe_curve, main
from tabletcfg.proc import TabletError
from tabletcfg.profiles import Profile, Store


class ActiveProfileTest(unittest.TestCase):
    STORE = Store("padrao", {"padrao": Profile(), "trabalho": Profile()})

    def test_explicit_wins(self):
        self.assertEqual(active_profile(self.STORE, "trabalho", "padrao"), "trabalho")

    def test_explicit_missing_is_error(self):
        with self.assertRaises(TabletError):
            active_profile(self.STORE, "sumiu", None)

    def test_last_applied_then_saved(self):
        self.assertEqual(active_profile(self.STORE, None, "trabalho"), "trabalho")
        self.assertEqual(active_profile(self.STORE, None, "sumiu"), "padrao")

    def test_nothing_is_error(self):
        with self.assertRaises(TabletError):
            active_profile(Store(None, {"a": Profile()}), None, None)


class DescribeTest(unittest.TestCase):
    def test_preset_and_custom(self):
        self.assertEqual(describe_curve((0.4, 0.0, 1.0, 0.6)), "Firme (+50)  [0.4 0 1 0.6]")
        self.assertEqual(describe_curve((0.0, 0.0, 1.0, 1.0)), "Normal (0)  [0 0 1 1]")
        self.assertEqual(describe_curve((0.3, 0.1, 0.6, 0.9)), "Personalizada  [0.3 0.1 0.6 0.9]")


class PressureCommandTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.dir.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.dir.cleanup)
        profiles.save(Store("padrao", {"padrao": Profile(), "trabalho": Profile()}))

    def run_cli(self, *argv, last="padrao", apply_error=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("tabletcfg.cli.ap.read_last", return_value=last), \
             mock.patch("tabletcfg.cli.ap.apply_curve", side_effect=apply_error) as apply_curve, \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["pressure", *argv])
        return code, out.getvalue(), err.getvalue(), apply_curve

    def curve(self, name):
        return profiles.load().profiles[name].pressure_curve

    def test_preset_saves_and_applies_active_profile(self):
        code, out, _, apply_curve = self.run_cli("firme")
        self.assertEqual(code, 0)
        self.assertEqual(self.curve("padrao"), (0.4, 0.0, 1.0, 0.6))
        apply_curve.assert_called_once_with((0.4, 0.0, 1.0, 0.6))
        self.assertIn("Firme", out)

    def test_custom_curve(self):
        self.run_cli("--curve", "0.2", "0", "1", "0.8")
        self.assertEqual(self.curve("padrao"), (0.2, 0.0, 1.0, 0.8))

    def test_other_profile_is_saved_but_not_applied(self):
        code, out, _, apply_curve = self.run_cli("-30", "--profile", "trabalho")
        self.assertEqual(code, 0)
        self.assertEqual(self.curve("trabalho"), (0.0, 0.24, 0.76, 1.0))
        apply_curve.assert_not_called()
        self.assertIn("tabletcfg apply trabalho", out)

    def test_pen_missing_still_saves(self):
        code, _, err, _ = self.run_cli("macia", apply_error=PenNotReady("sem caneta"))
        self.assertEqual(code, 0)
        self.assertEqual(self.curve("padrao"), (0.0, 0.4, 0.6, 1.0))
        self.assertIn("tabletcfg apply padrao", err)

    def test_invalid_changes_nothing(self):
        for argv in (("duro",), ("--curve", "0.9", "0", "0.1", "1"), ("firme", "--curve", "0", "0", "1", "1")):
            with self.subTest(argv=argv):
                code, _, err, apply_curve = self.run_cli(*argv)
                self.assertNotEqual(code, 0)
                self.assertEqual(self.curve("padrao"), (0.0, 0.0, 1.0, 1.0))
                apply_curve.assert_not_called()

    def test_show_without_arguments(self):
        with mock.patch("tabletcfg.cli.ap.read_pen_curve", return_value=None):
            code, out, _, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("Perfil 'padrao': Normal", out)
        self.assertIn("caneta não detectada", out)


if __name__ == "__main__":
    unittest.main()
