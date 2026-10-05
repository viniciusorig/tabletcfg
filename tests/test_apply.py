import os
import unittest
from unittest import mock

from tabletcfg.apply import (
    PenNotReady, apply_profile, compute_for_profile, follow_apply, next_name, parse_env,
    refresh_session,
)
from tabletcfg.devices import Tablet
from tabletcfg.proc import CommandError
from tabletcfg.matrix import transform
from tabletcfg.monitors import Layout, Monitor
from tabletcfg.profiles import Profile

LAYOUT = Layout(4480, 1440, (
    Monitor("DP-2", "HKM-2400-00000001", 0, 0, 1920, 1080, False),
    Monitor("DP-4", "SKG-2783-000F69B5", 1920, 0, 2560, 1440, True),
))


class ComputeTest(unittest.TestCase):
    def test_profile_on_dp4(self):
        p = Profile(monitor_id="SKG-2783-000F69B5", monitor_name="DP-4", keep_aspect=False)
        res = compute_for_profile(p, LAYOUT, (204.0, 136.0))
        self.assertEqual(res.warnings, [])
        x, y = transform(res.matrix, 0, 0)
        self.assertAlmostEqual(x, 1920 / 4480)

    def test_missing_monitor_warns(self):
        p = Profile(monitor_id="X", monitor_name="HDMI-9")
        res = compute_for_profile(p, LAYOUT, (204.0, 136.0))
        self.assertTrue(any("HDMI-9" in w for w in res.warnings))

    def test_unknown_tablet_size_ignores_keep_aspect(self):
        p = Profile(target="all", keep_aspect=True)
        res = compute_for_profile(p, LAYOUT, None)
        self.assertTrue(any("proporção" in w for w in res.warnings))
        self.assertEqual([round(v, 6) for v in res.matrix], [1, 0, 0, 0, 1, 0, 0, 0, 1])


class HelpersTest(unittest.TestCase):
    def test_parse_env(self):
        env = parse_env("DISPLAY=:0\nXAUTHORITY=/run/user/1000/lyxauth\nX=a=b\n")
        self.assertEqual(env["DISPLAY"], ":0")
        self.assertEqual(env["X"], "a=b")

    def test_next_name_cycles(self):
        self.assertEqual(next_name(["a", "b", "c"], "b"), "c")
        self.assertEqual(next_name(["a", "b", "c"], "c"), "a")
        self.assertEqual(next_name(["a", "b"], "sumiu"), "a")
        self.assertIsNone(next_name([], None))

    def test_refresh_session_overrides_stale_display(self):
        env = "DISPLAY=:1\nXAUTHORITY=/run/user/1000/novo\n"
        with mock.patch.dict(os.environ, {"DISPLAY": ":0", "XAUTHORITY": "/velho"}, clear=True), \
             mock.patch("tabletcfg.apply.run", return_value=env):
            refresh_session()
            self.assertEqual(os.environ["DISPLAY"], ":1")
            self.assertEqual(os.environ["XAUTHORITY"], "/run/user/1000/novo")

    def test_refresh_session_keeps_env_when_systemd_has_none(self):
        with mock.patch.dict(os.environ, {"DISPLAY": ":0"}, clear=True), \
             mock.patch("tabletcfg.apply.run", return_value=""):
            refresh_session()
            self.assertEqual(os.environ["DISPLAY"], ":0")


class FollowTest(unittest.TestCase):
    def run_follow(self, outcomes, present=None):
        """outcomes: exceções (ou None = sucesso) devolvidas a cada tentativa."""
        outcomes = iter(outcomes)
        present = iter(present) if present is not None else None
        log, attempts = [], []

        def apply_once():
            attempts.append(1)
            exc = next(outcomes)
            if exc:
                raise exc

        ok = follow_apply(apply_once, lambda: next(present) if present else True,
                          refresh=lambda: None, log=log.append, sleep=lambda s: None)
        return ok, log, len(attempts)

    def test_applies_once_pen_appears(self):
        ok, log, n = self.run_follow([PenNotReady("sem caneta")] * 3 + [None])
        self.assertTrue(ok)
        self.assertEqual(n, 4)
        self.assertEqual(log, ["sem caneta"])  # mesma mensagem registrada uma vez só

    def test_logs_each_distinct_error(self):
        ok, log, _ = self.run_follow([CommandError("X recusou"), PenNotReady("sem caneta"), None])
        self.assertEqual(log, ["X recusou", "sem caneta"])

    def test_stops_when_tablet_unplugged(self):
        ok, log, n = self.run_follow([PenNotReady("sem caneta")] * 5, present=[True, True, False])
        self.assertFalse(ok)
        self.assertEqual(n, 2)
        self.assertIn("desconectada", log[-1])


class ApplyProfileTest(unittest.TestCase):
    def test_pen_not_ready_before_first_proximity(self):
        t = Tablet((), "T505", ("/dev/input/event27",), "08f2", "6811", (204.0, 136.0))
        with self.assertRaises(PenNotReady) as cm:
            apply_profile(Profile(target="all"), t, LAYOUT)
        self.assertIn("caneta", str(cm.exception))

    def test_sets_matrix_on_every_pen_device(self):
        t = Tablet((23, 30), "T505", ("/dev/input/event27",), "08f2", "6811", (204.0, 136.0))
        with mock.patch("tabletcfg.apply.set_ctm") as set_ctm:
            apply_profile(Profile(target="all", keep_aspect=False), t, LAYOUT)
        self.assertEqual([c.args[0] for c in set_ctm.call_args_list], [23, 30])


if __name__ == "__main__":
    unittest.main()
