import unittest

from tabletcfg.buttons import BUILTIN, Learner, Remapper, parse_action
from tabletcfg.evdev import BTN_RIGHT, EV_KEY, EV_REL, REL_HWHEEL, REL_WHEEL

T505 = BUILTIN["08f2:6811"]
CTRL, Z, Y, TAB, SHIFT, S, ALT, KPMINUS = 29, 44, 21, 15, 42, 31, 56, 74


def down(*codes):
    return [(EV_KEY, c, 1) for c in codes]


def up(*codes):
    return [(EV_KEY, c, 0) for c in codes]


def rep(*codes):
    return [(EV_KEY, c, 2) for c in codes]


def remapper(**actions):
    return Remapper(T505, {b: parse_action(a) for b, a in actions.items()})


class RemapperTest(unittest.TestCase):
    def test_unmapped_button_passes_original_keys(self):
        r = remapper()
        self.assertEqual(r.feed(down(CTRL, Z)).events, down(CTRL, Z))
        self.assertEqual(r.feed(up(CTRL, Z)).events, up(Z, CTRL))

    def test_shortcut_press_hold_release(self):
        r = remapper(tablet5="key ctrl+shift+s")  # Tab
        self.assertEqual(r.feed(down(TAB)).events, down(CTRL, SHIFT, S))
        self.assertEqual(r.feed(rep(TAB)).events, rep(S))
        self.assertEqual(r.feed(up(TAB)).events, up(S, SHIFT, CTRL))

    def test_modifier_only_button_can_be_remapped(self):
        r = remapper(tablet7="key shift")  # botão que envia só Ctrl
        self.assertEqual(r.feed(down(CTRL)).events, down(SHIFT))
        self.assertEqual(r.feed(up(CTRL)).events, up(SHIFT))

    def test_pen_button_click_holds_for_drag(self):
        r = remapper(pen1="click right")  # Ctrl+Y
        self.assertEqual(r.feed(down(CTRL, Y)).events, [(EV_KEY, BTN_RIGHT, 1)])
        self.assertEqual(r.feed(rep(Y)).events, [])
        self.assertEqual(r.feed(up(CTRL, Y)).events, [(EV_KEY, BTN_RIGHT, 0)])

    def test_scroll_repeats_while_held(self):
        r = remapper(tablet1="scroll down", tablet2="scroll right")
        self.assertEqual(r.feed(down(CTRL, KPMINUS)).events, [(EV_REL, REL_WHEEL, -1)])
        self.assertEqual(r.feed(rep(KPMINUS)).events, [(EV_REL, REL_WHEEL, -1)])
        self.assertEqual(r.feed(up(CTRL, KPMINUS)).events, [])
        self.assertEqual(r.feed(down(CTRL, 78)).events, [(EV_REL, REL_HWHEEL, 1)])

    def test_command_runs_once_on_press(self):
        r = remapper(pen2="command tabletcfg next")
        out = r.feed(down(CTRL, Z))
        self.assertEqual((out.events, out.commands), ([], ["tabletcfg next"]))
        self.assertEqual(r.feed(rep(Z)).commands, [])
        self.assertEqual(r.feed(up(CTRL, Z)).commands, [])

    def test_disable_swallows_everything(self):
        r = remapper(tablet8="disable")
        for frame in (down(ALT), rep(ALT), up(ALT)):
            self.assertEqual(r.feed(frame).events, [])

    def test_unknown_keys_pass_through(self):
        r = remapper(tablet5="disable")
        self.assertEqual(r.feed(down(30)).events, down(30))
        self.assertEqual(r.feed(rep(30)).events, rep(30))
        self.assertEqual(r.feed(up(30)).events, up(30))

    def test_non_key_events_ignored(self):
        self.assertEqual(remapper().feed([(4, 4, 458976)]).events, [])  # EV_MSC

    def test_release_uses_action_from_press_time(self):
        r = remapper(tablet5="key ctrl+shift+s")
        r.feed(down(TAB))
        r.set_actions({})  # perfil trocado com o botão segurado
        self.assertEqual(r.feed(up(TAB)).events, up(S, SHIFT, CTRL))

    def test_release_all(self):
        r = remapper(pen1="click right", tablet5="key ctrl+shift+s")
        r.feed(down(CTRL, Y))
        r.feed(down(TAB))
        self.assertCountEqual(r.release_all().events,
                              [(EV_KEY, BTN_RIGHT, 0)] + up(S, SHIFT, CTRL))
        self.assertEqual(r.release_all().events, [])


class LearnerTest(unittest.TestCase):
    def test_learns_tablet_then_pen(self):
        l = Learner()
        self.assertEqual(l.feed(down(TAB)), ("added", "tablet1"))
        self.assertIsNone(l.feed(up(TAB)))
        self.assertEqual(l.feed(down(CTRL, Z)), ("added", "tablet2"))
        l.next_phase()
        self.assertEqual(l.feed(down(CTRL, Y)), ("added", "pen1"))
        m = l.result()
        self.assertEqual(m.tablet, (frozenset({TAB}), frozenset({CTRL, Z})))
        self.assertEqual(m.pen, (frozenset({CTRL, Y}),))

    def test_repeated_signature_is_reported_not_added(self):
        l = Learner()
        l.feed(down(TAB))
        self.assertEqual(l.feed(down(TAB)), ("repeat", "tablet1"))
        l.next_phase()
        self.assertEqual(l.feed(down(TAB)), ("repeat", "tablet1"))
        self.assertEqual(l.result().pen, ())

    def test_autorepeat_ignored(self):
        l = Learner()
        l.feed(down(TAB))
        self.assertIsNone(l.feed(rep(TAB)))


if __name__ == "__main__":
    unittest.main()
