import unittest

from tabletcfg.buttons import BUILTIN, parse_action
from tabletcfg.evdev import BTN_RIGHT, EV_KEY
from tabletcfg.profiles import Profile, ProfileError, Store
from tabletcfg.remap import ButtonService, actions_for

T505 = BUILTIN["08f2:6811"]
CTRL, Y, TAB = 29, 21, 15


class FakeDevice:
    def __init__(self, frames=()):
        self.frames = list(frames)
        self.grabbed = False

    def grab(self, on=True):
        self.grabbed = on

    def read_frames(self):
        if self.frames and self.frames[0] == "gone":
            raise OSError(19, "No such device")
        out, self.frames = self.frames, []
        return out


class FakeUInput:
    def __init__(self):
        self.sent = []

    def emit(self, events):
        if events:
            self.sent.append(events)


class ActionsForTest(unittest.TestCase):
    STORE = Store("padrao", {"padrao": Profile(buttons={"pen1": "click right"}),
                             "krita": Profile(buttons={"tablet5": "key ctrl+z",
                                                       "tablet12": "disable"})})

    def test_last_applied_profile_wins(self):
        name, actions, warns = actions_for(T505, self.STORE, "krita")
        self.assertEqual(name, "krita")
        self.assertEqual(actions, {"tablet5": parse_action("key ctrl+z")})
        self.assertTrue(any("tablet12" in w for w in warns))

    def test_falls_back_to_saved(self):
        name, actions, _ = actions_for(T505, self.STORE, "sumiu")
        self.assertEqual((name, actions), ("padrao", {"pen1": parse_action("click right")}))

    def test_no_profile(self):
        self.assertEqual(actions_for(T505, Store(), None), (None, {}, []))


class ServiceTest(unittest.TestCase):
    def make(self, actions, frames=()):
        self.config = {"actions": actions}
        self.dev = FakeDevice(frames)
        self.ui = FakeUInput()
        self.ran, self.logs = [], []

        def load():
            if isinstance(self.config["actions"], Exception):
                raise self.config["actions"]
            return "p", self.config["actions"], []

        return ButtonService(T505, [self.dev], self.ui, load, self.ran.append, self.logs.append)

    def test_grabs_only_when_profile_has_actions(self):
        s = self.make({})
        s.reload()
        self.assertFalse(self.dev.grabbed)
        self.config["actions"] = {"pen1": parse_action("click right")}
        s.reload()
        self.assertTrue(self.dev.grabbed)

    def test_remaps_and_runs_commands(self):
        s = self.make({"pen1": parse_action("click right"),
                       "tablet5": parse_action("command tabletcfg next")},
                      [[(EV_KEY, CTRL, 1), (EV_KEY, Y, 1)], [(EV_KEY, TAB, 1)]])
        s.reload()
        self.assertTrue(s.poll([self.dev]))
        self.assertEqual(self.ui.sent, [[(EV_KEY, BTN_RIGHT, 1)]])
        self.assertEqual(self.ran, ["tabletcfg next"])

    def test_ignores_frames_when_not_grabbed(self):
        s = self.make({}, [[(EV_KEY, TAB, 1)]])
        s.reload()
        s.poll([self.dev])
        self.assertEqual(self.ui.sent, [])

    def test_ungrab_releases_held_buttons(self):
        s = self.make({"pen1": parse_action("click right")}, [[(EV_KEY, CTRL, 1), (EV_KEY, Y, 1)]])
        s.reload()
        s.poll([self.dev])
        self.config["actions"] = {}
        s.reload()
        self.assertEqual(self.ui.sent[-1], [(EV_KEY, BTN_RIGHT, 0)])
        self.assertFalse(self.dev.grabbed)

    def test_bad_profile_keeps_previous_config(self):
        s = self.make({"pen1": parse_action("click right")})
        s.reload()
        self.config["actions"] = ProfileError("perfil quebrado")
        s.reload()
        self.assertTrue(self.dev.grabbed)
        self.assertIn("perfil quebrado", self.logs[-1])

    def test_disconnect_stops(self):
        s = self.make({}, ["gone"])
        s.reload()
        self.assertFalse(s.poll([self.dev]))


if __name__ == "__main__":
    unittest.main()
