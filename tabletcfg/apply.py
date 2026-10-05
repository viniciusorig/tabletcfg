"""Perfil → matriz → xinput, e esperas usadas pelo serviço automático."""
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .devices import Tablet, find_tablet, set_ctm
from .matrix import IDENTITY, compute_ctm
from .monitors import Layout, read_layout, resolve_target
from .proc import TabletError, run
from .profiles import Profile


class NoTablet(TabletError):
    pass


@dataclass
class ApplyResult:
    matrix: list[float]
    warnings: list[str]


def compute_for_profile(profile: Profile, layout: Layout,
                        tablet_mm: tuple[float, float] | None) -> ApplyResult:
    rect, warn = resolve_target(layout, profile.target, profile.monitor_id, profile.monitor_name)
    warnings = [warn] if warn else []
    keep = profile.keep_aspect
    if keep and tablet_mm is None:
        warnings.append("Tamanho físico da mesa desconhecido; 'manter proporção' ignorado")
        keep = False
    m = compute_ctm((layout.width, layout.height), rect, profile.screen_area,
                    profile.tablet_area, profile.rotation, keep, tablet_mm or (1.0, 1.0))
    return ApplyResult(m, warnings)


def _require(tablet: Tablet | None) -> Tablet:
    tablet = tablet or find_tablet()
    if tablet is None:
        raise NoTablet("Mesa digitalizadora não encontrada (está conectada?)")
    return tablet


def apply_profile(profile: Profile, tablet: Tablet | None = None,
                  layout: Layout | None = None) -> ApplyResult:
    tablet = _require(tablet)
    res = compute_for_profile(profile, layout or read_layout(), tablet.size_mm)
    set_ctm(tablet.xinput_id, res.matrix)
    return res


def reset(tablet: Tablet | None = None) -> None:
    set_ctm(_require(tablet).xinput_id, IDENTITY)


def parse_env(text: str) -> dict[str, str]:
    env = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            env[key] = value
    return env


def wait_for_session(timeout: float, sleep=time.sleep, clock=time.monotonic) -> bool:
    """Garante DISPLAY/XAUTHORITY no ambiente, buscando no systemd do usuário."""
    deadline = clock() + timeout
    while True:
        if os.environ.get("DISPLAY"):
            return True
        env = parse_env(run(["systemctl", "--user", "show-environment"], check=False))
        if env.get("DISPLAY"):
            os.environ["DISPLAY"] = env["DISPLAY"]
            if env.get("XAUTHORITY"):
                os.environ["XAUTHORITY"] = env["XAUTHORITY"]
            return True
        if clock() >= deadline:
            return False
        sleep(0.5)


def wait_for_tablet(timeout: float, sleep=time.sleep, clock=time.monotonic) -> Tablet | None:
    deadline = clock() + timeout
    while True:
        try:
            if t := find_tablet():
                return t
        except TabletError:
            pass  # X ainda subindo
        if clock() >= deadline:
            return None
        sleep(0.5)


def _state_file() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "tabletcfg" / "last"


def read_last() -> str | None:
    try:
        return _state_file().read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def write_last(name: str) -> None:
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(name + "\n", encoding="utf-8")


def next_name(names: list[str], current: str | None) -> str | None:
    if not names:
        return None
    if current in names:
        return names[(names.index(current) + 1) % len(names)]
    return names[0]
