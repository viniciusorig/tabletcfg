import os
import unittest
from unittest import mock

from tabletcfg.apply import (
    compute_for_profile, next_name, parse_env, wait_for_session,
)
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

    def test_wait_for_session_reads_systemd_env(self):
        t = [0.0]
        outputs = iter(["", "DISPLAY=:0\nXAUTHORITY=/tmp/xa\n"])
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch("tabletcfg.apply.run", side_effect=lambda *a, **k: next(outputs)):
            ok = wait_for_session(5, sleep=lambda s: t.__setitem__(0, t[0] + s),
                                  clock=lambda: t[0])
            self.assertTrue(ok)
            self.assertEqual(os.environ["DISPLAY"], ":0")
            self.assertEqual(os.environ["XAUTHORITY"], "/tmp/xa")

    def test_wait_for_session_times_out(self):
        t = [0.0]
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch("tabletcfg.apply.run", return_value=""):
            ok = wait_for_session(2, sleep=lambda s: t.__setitem__(0, t[0] + s),
                                  clock=lambda: t[0])
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
