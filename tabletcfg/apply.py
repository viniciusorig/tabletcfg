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


class PenNotReady(TabletError):
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
    if not tablet.xinput_ids:
        raise PenNotReady("Aproxime a caneta da mesa e tente de novo "
                          "(o X só cria o dispositivo da caneta depois disso)")
    return tablet


def _set_all(tablet: Tablet, matrix: list[float]) -> None:
    for xid in tablet.xinput_ids:
        set_ctm(xid, matrix)


def apply_profile(profile: Profile, tablet: Tablet | None = None,
                  layout: Layout | None = None) -> ApplyResult:
    tablet = _require(tablet)
    res = compute_for_profile(profile, layout or read_layout(), tablet.size_mm)
    _set_all(tablet, res.matrix)
    return res


def reset(tablet: Tablet | None = None) -> None:
    _set_all(_require(tablet), IDENTITY)


def parse_env(text: str) -> dict[str, str]:
    env = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            env[key] = value
    return env


def refresh_session() -> None:
    """Copia DISPLAY/XAUTHORITY do systemd do usuário (pode mudar a cada login)."""
    env = parse_env(run(["systemctl", "--user", "show-environment"], check=False))
    for key in ("DISPLAY", "XAUTHORITY"):
        if env.get(key):
            os.environ[key] = env[key]


def follow_apply(apply_once, tablet_present, refresh=refresh_session, log=print,
                 sleep=time.sleep, interval: float = 1.0) -> bool:
    """Tenta aplicar até conseguir; desiste só se a mesa for desconectada."""
    last = None
    while tablet_present():
        refresh()
        try:
            apply_once()
            return True
        except TabletError as e:
            if str(e) != last:
                last = str(e)
                log(last)
        sleep(interval)
    log("Mesa desconectada; nada aplicado")
    return False


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
