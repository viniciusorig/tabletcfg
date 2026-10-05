"""Encontra a caneta da mesa no xinput e aplica a matriz."""
import re
from dataclasses import dataclass

from .proc import run

SLAVE_POINTER_RE = re.compile(r"↳\s+(.*?)\s+id=(\d+)\s+\[slave\s+pointer")
NODE_RE = re.compile(r'Device Node \(\d+\):\s+"([^"]+)"')
PEN_RE = re.compile(r"\b(pen|stylus)\b", re.IGNORECASE)
CTM_PROP = "Coordinate Transformation Matrix"


@dataclass(frozen=True)
class Tablet:
    xinput_id: int
    name: str
    node: str | None
    vendor: str | None
    product: str | None
    size_mm: tuple[float, float] | None


def parse_pointer_devices(text: str) -> list[tuple[int, str]]:
    out = []
    for line in text.splitlines():
        if m := SLAVE_POINTER_RE.search(line):
            out.append((int(m.group(2)), m.group(1)))
    return out


def order_candidates(devs: list[tuple[int, str]]) -> list[tuple[int, str]]:
    devs = [d for d in devs if "XTEST" not in d[1]]
    return sorted(devs, key=lambda d: not PEN_RE.search(d[1]))


def parse_device_node(text: str) -> str | None:
    m = NODE_RE.search(text)
    return m.group(1) if m else None


def tablet_from_udev(xinput_id: int, name: str, node: str, props: dict) -> Tablet | None:
    if props.get("ID_INPUT_TABLET") != "1" or props.get("ID_INPUT_TABLET_PAD") == "1":
        return None
    size = None
    try:
        w, h = float(props["ID_INPUT_WIDTH_MM"]), float(props["ID_INPUT_HEIGHT_MM"])
        if w > 0 and h > 0:
            size = (w, h)
    except (KeyError, ValueError):
        pass
    return Tablet(xinput_id, name, node, props.get("ID_VENDOR_ID"),
                  props.get("ID_MODEL_ID"), size)


def _udev_props(node: str) -> dict:
    import pyudev
    try:
        dev = pyudev.Devices.from_device_file(pyudev.Context(), node)
    except (pyudev.DeviceNotFoundError, OSError, ValueError):
        return {}
    return dict(dev.properties)


def find_tablet() -> Tablet | None:
    for xid, name in order_candidates(parse_pointer_devices(run(["xinput", "list"]))):
        node = parse_device_node(run(["xinput", "list-props", str(xid)], check=False))
        if node and (t := tablet_from_udev(xid, name, node, _udev_props(node))):
            return t
    return None


def set_ctm(xinput_id: int, matrix: list[float]) -> None:
    run(["xinput", "set-prop", str(xinput_id), CTM_PROP, *(f"{v:.6f}" for v in matrix)])
