"""Encontra a mesa (via udev) e os dispositivos da caneta no xinput.

O xf86-input-libinput só cria o dispositivo "... Pen (0)" no X quando a caneta
chega perto da mesa pela primeira vez; por isso a identidade da mesa vem do
udev e a lista de ids do xinput pode estar vazia.
"""
import re
from dataclasses import dataclass

from .pressure import Curve, from_prop, to_prop
from .proc import run

SLAVE_POINTER_RE = re.compile(r"↳\s+(.*?)\s+id=(\d+)\s+\[slave\s+pointer")
NODE_RE = re.compile(r'Device Node \(\d+\):\s+"([^"]+)"')
CTM_PROP = "Coordinate Transformation Matrix"
PRESSURE_PROP = "libinput Tablet Tool Pressurecurve"
PRESSURE_RE = re.compile(re.escape(PRESSURE_PROP) + r" \(\d+\):\s+(.*)")


@dataclass(frozen=True)
class Tablet:
    xinput_ids: tuple[int, ...]  # ponteiros da caneta; vazio até a 1ª aproximação
    name: str
    nodes: tuple[str, ...]
    vendor: str | None
    product: str | None
    size_mm: tuple[float, float] | None


def parse_pointer_devices(text: str) -> list[tuple[int, str]]:
    out = []
    for line in text.splitlines():
        if m := SLAVE_POINTER_RE.search(line):
            out.append((int(m.group(2)), m.group(1)))
    return out


def parse_device_node(text: str) -> str | None:
    m = NODE_RE.search(text)
    return m.group(1) if m else None


def parse_pressure_curve(text: str) -> Curve | None:
    m = PRESSURE_RE.search(text)
    if not m:
        return None
    try:
        return from_prop([float(v) for v in m.group(1).split(",")])
    except ValueError:
        return None


def _size(props: dict) -> tuple[float, float] | None:
    try:
        w, h = float(props["ID_INPUT_WIDTH_MM"]), float(props["ID_INPUT_HEIGHT_MM"])
    except (KeyError, ValueError):
        return None
    return (w, h) if w > 0 and h > 0 else None


def select_tablet(udev_devs: list[dict], pointers: list[tuple[int, str, str | None]]) -> Tablet | None:
    """udev_devs: propriedades dos dispositivos de input; pointers: (id, nome, nó) do xinput."""
    tabs = [d for d in udev_devs
            if d.get("ID_INPUT_TABLET") == "1" and d.get("ID_INPUT_TABLET_PAD") != "1"
            and d.get("DEVNAME", "").startswith("/dev/input/event")]
    if not tabs:
        return None
    ident = (tabs[0].get("ID_VENDOR_ID"), tabs[0].get("ID_MODEL_ID"))
    tabs = sorted((d for d in tabs if (d.get("ID_VENDOR_ID"), d.get("ID_MODEL_ID")) == ident),
                  key=lambda d: d["DEVNAME"])
    nodes = tuple(d["DEVNAME"] for d in tabs)
    ids = tuple(xid for xid, _, node in pointers if node in nodes)
    pen_nodes = {node for _, _, node in pointers if node in nodes}
    sized = [d for d in tabs if _size(d)]
    sized.sort(key=lambda d: d["DEVNAME"] not in pen_nodes)
    name = tabs[0].get("NAME", "").strip('"') or "Mesa digitalizadora"
    return Tablet(ids, name, nodes, ident[0], ident[1], _size(sized[0]) if sized else None)


def select_button_nodes(udev_devs: list[dict], vendor: str, product: str) -> list[str]:
    """Nós evdev de onde vêm os botões: teclado ou pad do mesmo modelo (nunca a caneta)."""
    out = []
    for d in udev_devs:
        if ((d.get("ID_VENDOR_ID"), d.get("ID_MODEL_ID")) != (vendor, product)
                or not d.get("DEVNAME", "").startswith("/dev/input/event")):
            continue
        pad = d.get("ID_INPUT_TABLET_PAD") == "1"
        if pad or (d.get("ID_INPUT_KEY") == "1" and d.get("ID_INPUT_TABLET") != "1"
                   and d.get("ID_INPUT_MOUSE") != "1"):
            out.append(d["DEVNAME"])
    return sorted(out)


def button_nodes(tablet: Tablet) -> list[str]:
    import pyudev
    devs = [dict(dev.properties) for dev in pyudev.Context().list_devices(subsystem="input")]
    return select_button_nodes(devs, tablet.vendor, tablet.product)


def _udev_devices() -> list[dict]:
    import pyudev
    ctx = pyudev.Context()
    out = []
    for dev in ctx.list_devices(subsystem="input", ID_INPUT_TABLET="1"):
        props = dict(dev.properties)
        if dev.parent is not None and "NAME" in dev.parent.properties:
            props.setdefault("NAME", dev.parent.properties["NAME"])
        out.append(props)
    return out


def tablet_present() -> bool:
    """Só udev, sem X: usado pelo serviço para saber se continua esperando."""
    return select_tablet(_udev_devices(), []) is not None


def find_tablet() -> Tablet | None:
    udev = _udev_devices()
    if select_tablet(udev, []) is None:
        return None
    pointers = []
    for xid, name in parse_pointer_devices(run(["xinput", "list"])):
        if "XTEST" not in name:
            node = parse_device_node(run(["xinput", "list-props", str(xid)], check=False))
            pointers.append((xid, name, node))
    return select_tablet(udev, pointers)


def set_ctm(xinput_id: int, matrix: list[float]) -> None:
    run(["xinput", "set-prop", str(xinput_id), CTM_PROP, *(f"{v:.6f}" for v in matrix)])


def read_curve(xinput_id: int) -> Curve | None:
    """Curva atual do dispositivo, ou None se ele não tem a propriedade de pressão."""
    return parse_pressure_curve(run(["xinput", "list-props", str(xinput_id)], check=False))


def set_curve(xinput_id: int, curve: Curve) -> None:
    run(["xinput", "set-prop", str(xinput_id), PRESSURE_PROP,
         *(f"{v:.6f}" for v in to_prop(curve))])
