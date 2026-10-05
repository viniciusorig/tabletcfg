import tempfile
import unittest
from pathlib import Path

from tabletcfg.profiles import (
    Profile, ProfileError, Store, backup, dumps, load, save, validate,
)


class ProfilesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "sub" / "profiles.toml"

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_is_empty_store(self):
        store = load(self.path)
        self.assertIsNone(store.saved)
        self.assertEqual(store.profiles, {})

    def test_round_trip(self):
        p = Profile("monitor", "SKG-2783-000F69B5", "DP-4", (0.1, 0.2, 0.5, 0.5),
                    (0.0, 0.0, 0.75, 1.0), 90, False)
        store = Store("desenho", {"desenho": p, "Ação \"rápida\"": Profile(target="all")})
        save(store, self.path)
        back = load(self.path)
        self.assertEqual(back.saved, "desenho")
        self.assertEqual(back.profiles["desenho"], p)
        self.assertEqual(back.profiles["Ação \"rápida\""].target, "all")

    def test_save_is_atomic_no_temp_left(self):
        save(Store(None, {"a": Profile()}), self.path)
        self.assertEqual([f.name for f in self.path.parent.iterdir()], ["profiles.toml"])

    def test_saved_pointing_to_missing_profile_becomes_none(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('saved = "sumiu"\n[profiles.a]\nrotation = 0\n')
        self.assertIsNone(load(self.path).saved)

    def test_invalid_values_raise_with_profile_name(self):
        bad = [
            "rotation = 45",
            'target = "metade"',
            "screen_area = [0.5, 0.0, 0.8, 1.0]",
            "tablet_area = [0.0, 0.0, 0.0, 1.0]",
            "tablet_area = [-0.1, 0.0, 0.5, 0.5]",
            "tablet_area = [0.0, 0.0, 1.0]",
            'keep_aspect = "sim"',
        ]
        for line in bad:
            with self.subTest(line=line):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(f"[profiles.ruim]\n{line}\n")
                with self.assertRaises(ProfileError) as cm:
                    load(self.path)
                self.assertIn("ruim", str(cm.exception))

    def test_syntax_error_mentions_line(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("[profiles.a]\nrotation = = 3\n")
        with self.assertRaises(ProfileError) as cm:
            load(self.path)
        self.assertIn("line 2", str(cm.exception))

    def test_validate_rejects_empty_name(self):
        with self.assertRaises(ProfileError):
            validate("  ", Profile())

    def test_backup_keeps_unreadable_file_before_overwrite(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("[profiles.a]\nrotation = 45\n")
        bak = backup(self.path)
        save(Store("b", {"b": Profile()}), self.path)
        self.assertEqual(bak.read_text(), "[profiles.a]\nrotation = 45\n")
        self.assertEqual(bak.name, "profiles.toml.bak")

    def test_backup_of_missing_file_is_none(self):
        self.assertIsNone(backup(self.path))

    def test_dumps_is_valid_toml_with_floats(self):
        text = dumps(Store(None, {"a": Profile(screen_area=(0, 0, 1, 1))}))
        self.assertIn("screen_area = [0.0, 0.0, 1.0, 1.0]", text)


if __name__ == "__main__":
    unittest.main()
