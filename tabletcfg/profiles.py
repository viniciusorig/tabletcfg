"""Perfis da mesa em ~/.config/tabletcfg/profiles.toml."""
import json
import math
import os
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .matrix import MIN_FRAC, Rect
from .proc import TabletError

TARGETS = ("monitor", "all")
ROTATIONS = (0, 90, 180, 270)
FULL: Rect = (0.0, 0.0, 1.0, 1.0)


class ProfileError(TabletError):
    pass


@dataclass
class Profile:
    target: str = "monitor"
    monitor_id: str = ""
    monitor_name: str = ""
    screen_area: Rect = FULL
    tablet_area: Rect = FULL
    rotation: int = 0
    keep_aspect: bool = True


@dataclass
class Store:
    saved: str | None = None
    profiles: dict[str, Profile] = field(default_factory=dict)


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "tabletcfg"


def default_path() -> Path:
    return config_dir() / "profiles.toml"


def _check_area(name: str, key: str, area) -> Rect:
    ok = (isinstance(area, (list, tuple)) and len(area) == 4
          and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                  and math.isfinite(v) for v in area))
    if ok:
        x, y, w, h = (float(v) for v in area)
        ok = (x >= 0 and y >= 0 and w >= MIN_FRAC - 1e-9 and h >= MIN_FRAC - 1e-9
              and x + w <= 1 + 1e-6 and y + h <= 1 + 1e-6)
    if not ok:
        raise ProfileError(f"Perfil '{name}': {key} inválido {area!r} "
                           f"(esperado [x, y, w, h] em frações dentro de 0..1)")
    return (x, y, w, h)


def validate(name: str, p: Profile) -> None:
    if not name.strip():
        raise ProfileError("Nome de perfil vazio")
    if p.target not in TARGETS:
        raise ProfileError(f"Perfil '{name}': target deve ser {' ou '.join(TARGETS)}")
    if type(p.rotation) is not int or p.rotation not in ROTATIONS:
        raise ProfileError(f"Perfil '{name}': rotation deve ser 0, 90, 180 ou 270")
    if not isinstance(p.keep_aspect, bool):
        raise ProfileError(f"Perfil '{name}': keep_aspect deve ser true ou false")
    if not isinstance(p.monitor_id, str) or not isinstance(p.monitor_name, str):
        raise ProfileError(f"Perfil '{name}': monitor_id/monitor_name devem ser texto")
    _check_area(name, "screen_area", p.screen_area)
    _check_area(name, "tablet_area", p.tablet_area)


def _from_dict(name: str, d: dict) -> Profile:
    if not isinstance(d, dict):
        raise ProfileError(f"Perfil '{name}' não é uma tabela")
    p = Profile(
        target=d.get("target", "monitor"),
        monitor_id=d.get("monitor_id", ""),
        monitor_name=d.get("monitor_name", ""),
        screen_area=d.get("screen_area", FULL),
        tablet_area=d.get("tablet_area", FULL),
        rotation=d.get("rotation", 0),
        keep_aspect=d.get("keep_aspect", True),
    )
    validate(name, p)
    p.screen_area = _check_area(name, "screen_area", p.screen_area)
    p.tablet_area = _check_area(name, "tablet_area", p.tablet_area)
    return p


def load(path: Path | None = None) -> Store:
    path = path or default_path()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Store()
    except tomllib.TOMLDecodeError as e:
        raise ProfileError(f"{path}: {e}") from None
    raw = data.get("profiles", {})
    if not isinstance(raw, dict):
        raise ProfileError(f"{path}: 'profiles' deve ser uma tabela")
    profiles = {name: _from_dict(name, d) for name, d in raw.items()}
    saved = data.get("saved")
    return Store(saved if saved in profiles else None, profiles)


def _s(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _area(a: Rect) -> str:
    return "[" + ", ".join(repr(round(float(v), 6)) for v in a) + "]"


def dumps(store: Store) -> str:
    out = ["# Gerado por tabletcfg"]
    if store.saved is not None:
        out.append(f"saved = {_s(store.saved)}")
    for name, p in store.profiles.items():
        out += [
            "",
            f"[profiles.{_s(name)}]",
            f"target = {_s(p.target)}",
            f"monitor_id = {_s(p.monitor_id)}",
            f"monitor_name = {_s(p.monitor_name)}",
            f"screen_area = {_area(p.screen_area)}",
            f"tablet_area = {_area(p.tablet_area)}",
            f"rotation = {p.rotation}",
            f"keep_aspect = {'true' if p.keep_aspect else 'false'}",
        ]
    return "\n".join(out) + "\n"


def save(store: Store, path: Path | None = None) -> None:
    path = path or default_path()
    for name, p in store.profiles.items():
        validate(name, p)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".profiles-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(dumps(store))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
