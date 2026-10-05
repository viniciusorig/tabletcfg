"""Monitores conectados, a partir de `xrandr --props`."""
import re
from dataclasses import dataclass

from .matrix import Rect
from .proc import run

SCREEN_RE = re.compile(r"^Screen \d+:.*current (\d+) x (\d+)")
OUTPUT_RE = re.compile(r"^(\S+) connected (primary )?(\d+)x(\d+)\+(\d+)\+(\d+)")
HEX_RE = re.compile(r"[0-9a-f]{2,}")
EDID_HEADER = bytes.fromhex("00ffffffffffff00")


@dataclass(frozen=True)
class Monitor:
    name: str
    id: str
    x: int
    y: int
    w: int
    h: int
    primary: bool

    @property
    def rect(self) -> Rect:
        return (self.x, self.y, self.w, self.h)


@dataclass(frozen=True)
class Layout:
    width: int
    height: int
    monitors: tuple[Monitor, ...]

    @property
    def rect(self) -> Rect:
        return (0, 0, self.width, self.height)


def edid_identity(edid: bytes) -> str | None:
    if len(edid) < 128 or edid[:8] != EDID_HEADER:
        return None
    m = int.from_bytes(edid[8:10], "big")
    mfg = "".join(chr(((m >> s) & 0x1F) + 64) for s in (10, 5, 0))
    product = int.from_bytes(edid[10:12], "little")
    serial = int.from_bytes(edid[12:16], "little")
    if serial:
        sid = f"{serial:08X}"
    else:
        sid = "0"
        for off in (54, 72, 90, 108):
            d = edid[off:off + 18]
            if d[:3] == b"\0\0\0" and d[3] == 0xFF:
                sid = d[5:18].split(b"\n")[0].decode("ascii", "replace").strip() or "0"
    return f"{mfg}-{product:04X}-{sid}"


def parse_xrandr(text: str) -> Layout:
    width = height = 0
    outputs = []  # [name, primary, w, h, x, y, edid_hex]
    current = None
    collecting = False
    for line in text.splitlines():
        if line[:1] and not line[:1].isspace():
            current = None
            collecting = False
            if s := SCREEN_RE.match(line):
                width, height = int(s.group(1)), int(s.group(2))
            elif o := OUTPUT_RE.match(line):
                current = [o.group(1), bool(o.group(2)), int(o.group(3)), int(o.group(4)),
                           int(o.group(5)), int(o.group(6)), ""]
                outputs.append(current)
            continue
        stripped = line.strip()
        if current is None:
            continue
        if stripped.startswith("EDID:"):
            collecting = True
        elif collecting and HEX_RE.fullmatch(stripped):
            current[6] += stripped
        else:
            collecting = False
    monitors = []
    for name, primary, w, h, x, y, edid_hex in outputs:
        ident = edid_identity(bytes.fromhex(edid_hex)) if edid_hex else None
        monitors.append(Monitor(name, ident or name, x, y, w, h, primary))
    monitors.sort(key=lambda m: (m.x, m.y))
    return Layout(width, height, tuple(monitors))


def find_monitor(layout: Layout, monitor_id: str, monitor_name: str) -> int | None:
    mons = layout.monitors
    for pred in (
        lambda m: monitor_id and m.id == monitor_id and m.name == monitor_name,
        lambda m: monitor_id and m.id == monitor_id,
        lambda m: monitor_name and m.name == monitor_name,
    ):
        for i, m in enumerate(mons):
            if pred(m):
                return i
    return None


def resolve_target(layout: Layout, target: str, monitor_id: str,
                   monitor_name: str) -> tuple[Rect, str | None]:
    if target == "all":
        return layout.rect, None
    i = find_monitor(layout, monitor_id, monitor_name)
    if i is None:
        who = monitor_name or monitor_id or "?"
        return layout.rect, f"Monitor {who} não encontrado; usando todos os monitores"
    return layout.monitors[i].rect, None


def read_layout() -> Layout:
    return parse_xrandr(run(["xrandr", "--props"]))
