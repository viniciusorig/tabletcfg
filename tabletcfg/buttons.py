"""Botões da mesa: ações por botão, mapa de botões por modelo e remapeamento (puro)."""
import json
import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .evdev import BTN_LEFT, BTN_MIDDLE, BTN_RIGHT, EV_KEY, EV_REL, REL_HWHEEL, REL_WHEEL
from .keys import (
    MODIFIERS, ComboError, code_of, combo_label, format_combo, name_of, parse_combo,
)
from .proc import TabletError


class ButtonError(TabletError):
    pass


CLICKS = {"left": "esquerdo", "middle": "do meio", "right": "direito"}
SCROLLS = {"up": "para cima", "down": "para baixo", "left": "para a esquerda",
           "right": "para a direita"}


@dataclass(frozen=True)
class Action:
    kind: str           # key | click | scroll | command | disable
    arg: object = None  # códigos | nome do botão/direção | linha de shell | None


def parse_action(text) -> Action:
    if not isinstance(text, str):
        raise ButtonError(f"Ação inválida {text!r} (esperado texto)")
    kind, _, rest = text.strip().partition(" ")
    rest = rest.strip()
    try:
        if kind == "key" and rest:
            return Action("key", parse_combo(rest))
    except ComboError as e:
        raise ButtonError(f"Ação inválida '{text}': {e}") from None
    if kind == "click" and rest in CLICKS:
        return Action("click", rest)
    if kind == "scroll" and rest in SCROLLS:
        return Action("scroll", rest)
    if kind == "command" and rest:
        return Action("command", rest)
    if kind == "disable" and not rest:
        return Action("disable")
    raise ButtonError(f"Ação inválida '{text}' (use key <atalho>, click left|middle|right, "
                      f"scroll up|down|left|right, command <comando> ou disable)")


def format_action(a: Action) -> str:
    if a.kind == "key":
        return f"key {format_combo(a.arg)}"
    if a.kind == "disable":
        return "disable"
    return f"{a.kind} {a.arg}"


def action_label(a: Action) -> str:
    if a.kind == "key":
        return f"Atalho {combo_label(a.arg)}"
    if a.kind == "click":
        return f"Clique {CLICKS[a.arg]}"
    if a.kind == "scroll":
        return f"Rolar {SCROLLS[a.arg]}"
    if a.kind == "command":
        return f"Comando: {a.arg}"
    return "Desativado"


Signature = frozenset[int]


@dataclass(frozen=True)
class ButtonMap:
    """Assinaturas dos botões em ordem física: mesa e caneta (da ponta para cima)."""
    tablet: tuple[Signature, ...]
    pen: tuple[Signature, ...]

    def ids(self) -> list[str]:
        return ([f"tablet{i}" for i in range(1, len(self.tablet) + 1)]
                + [f"pen{i}" for i in range(1, len(self.pen) + 1)])

    def signature(self, button: str) -> Signature | None:
        for prefix, sigs in (("tablet", self.tablet), ("pen", self.pen)):
            if button.startswith(prefix) and button[len(prefix):].isdigit():
                i = int(button[len(prefix):])
                return sigs[i - 1] if 1 <= i <= len(sigs) else None
        return None

    def lookup(self, sig: Signature) -> str | None:
        for button in self.ids():
            if self.signature(button) == sig:
                return button
        return None

    @staticmethod
    def label(button: str) -> str:
        if button.startswith("tablet"):
            return f"Mesa {button[6:]}"
        if button.startswith("pen"):
            return f"Caneta {button[3:]}"
        return button


def _sig(*names: str) -> Signature:
    return frozenset(code_of(n) for n in names)


# Capturado em 2026-10-07 (SZ PING-IT T505, clone do 10moon 1060N).
BUILTIN = {
    "08f2:6811": ButtonMap(
        tablet=(_sig("ctrl", "kp_subtract"), _sig("ctrl", "kp_add"), _sig("bracketleft"),
                _sig("bracketright"), _sig("tab"), _sig("space"), _sig("ctrl"), _sig("alt")),
        pen=(_sig("ctrl", "y"), _sig("ctrl", "z")),
    ),
}


def devices_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "tabletcfg" / "devices.toml"


def device_key(vendor: str, product: str) -> str:
    return f"{vendor.lower()}:{product.lower()}"


def _parse_sigs(key: str, field: str, raw) -> tuple[Signature, ...]:
    try:
        if not isinstance(raw, list):
            raise ButtonError("esperado uma lista")
        out = []
        for item in raw:
            if not isinstance(item, list) or not item or not all(isinstance(n, str) for n in item):
                raise ButtonError(f"botão inválido {item!r}")
            out.append(frozenset(code_of(n) for n in item))
        return tuple(out)
    except (ButtonError, ComboError) as e:
        raise ButtonError(f"devices.toml, [{key}] {field}: {e}") from None


def load_maps(path: Path | None = None) -> dict[str, ButtonMap]:
    path = path or devices_path()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as e:
        raise ButtonError(f"{path}: {e}") from None
    maps = {}
    for key, d in data.items():
        if not isinstance(d, dict):
            raise ButtonError(f"devices.toml: [{key}] deve ser uma tabela")
        maps[key.lower()] = ButtonMap(_parse_sigs(key, "tablet", d.get("tablet", [])),
                                      _parse_sigs(key, "pen", d.get("pen", [])))
    return maps


def _dump_sigs(sigs) -> str:
    items = ("[" + ", ".join(json.dumps(name_of(c)) for c in sorted(sig)) + "]" for sig in sigs)
    return "[" + ", ".join(items) + "]"


def save_maps(maps: dict[str, ButtonMap], path: Path | None = None) -> None:
    path = path or devices_path()
    out = ["# Botões aprendidos por modelo de mesa (gerado por tabletcfg)"]
    for key, m in sorted(maps.items()):
        out += ["", f"[{json.dumps(key)}]", f"tablet = {_dump_sigs(m.tablet)}",
                f"pen = {_dump_sigs(m.pen)}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".devices-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def map_for(vendor: str | None, product: str | None, path: Path | None = None) -> ButtonMap | None:
    """Mapa do modelo: o aprendido (devices.toml) tem prioridade sobre o embutido."""
    if not (vendor and product):
        return None
    key = device_key(vendor, product)
    return load_maps(path).get(key) or BUILTIN.get(key)


Event = tuple[int, int, int]  # (tipo, código, valor)
_CLICK_CODES = {"left": BTN_LEFT, "middle": BTN_MIDDLE, "right": BTN_RIGHT}
_SCROLL = {"up": (REL_WHEEL, 1), "down": (REL_WHEEL, -1),
           "left": (REL_HWHEEL, -1), "right": (REL_HWHEEL, 1)}


def _ordered(sig) -> list[int]:
    """Modificadores primeiro, como um teclado de verdade pressionaria."""
    return sorted(sig, key=lambda c: (c not in MODIFIERS, c))


@dataclass
class Output:
    events: list[Event]
    commands: list[str]


class Remapper:
    """Traduz pacotes de eventos do teclado da mesa nas ações do perfil."""

    def __init__(self, bmap: ButtonMap, actions: dict[str, Action]):
        self.bmap = bmap
        self.actions = actions
        self.active: dict[str, tuple[Signature, Action | None]] = {}

    def set_actions(self, actions: dict[str, Action]) -> None:
        self.actions = actions

    def feed(self, frame: list[Event]) -> Output:
        out = Output([], [])
        keys = [(code, value) for typ, code, value in frame if typ == EV_KEY]
        released: set[int] = set()  # teclas de botões já soltos neste pacote
        for code, value in keys:
            if value == 0 and code not in released:
                released |= self._key_up(code, out)
        downs = [code for code, value in keys if value == 1]
        if downs:
            button = self.bmap.lookup(frozenset(downs))
            if button is not None and button not in self.active:
                action = self.actions.get(button)
                self.active[button] = (frozenset(downs), action)
                self._press(frozenset(downs), action, out)
            else:
                out.events += [(EV_KEY, c, 1) for c in downs]
        repeated = set()
        for code, value in keys:
            if value == 2:
                button = self._owner(code)
                if button is None:
                    out.events.append((EV_KEY, code, 2))
                elif button not in repeated:
                    repeated.add(button)
                    self._repeat(*self.active[button], out)
        return out

    def release_all(self) -> Output:
        out = Output([], [])
        for button in list(self.active):
            sig, action = self.active.pop(button)
            self._release(sig, action, out)
        return out

    def _owner(self, code: int) -> str | None:
        return next((b for b, (sig, _) in self.active.items() if code in sig), None)

    def _key_up(self, code: int, out: Output) -> Signature:
        button = self._owner(code)
        if button is None:
            out.events.append((EV_KEY, code, 0))
            return frozenset()
        sig, action = self.active.pop(button)
        self._release(sig, action, out)
        return sig

    @staticmethod
    def _press(sig, action: Action | None, out: Output) -> None:
        if action is None or action.kind == "key":
            codes = _ordered(sig) if action is None else list(action.arg)
            out.events += [(EV_KEY, c, 1) for c in codes]
        elif action.kind == "click":
            out.events.append((EV_KEY, _CLICK_CODES[action.arg], 1))
        elif action.kind == "scroll":
            out.events.append((EV_REL, *_SCROLL[action.arg]))
        elif action.kind == "command":
            out.commands.append(action.arg)

    @staticmethod
    def _release(sig, action: Action | None, out: Output) -> None:
        if action is None or action.kind == "key":
            codes = _ordered(sig) if action is None else list(action.arg)
            out.events += [(EV_KEY, c, 0) for c in reversed(codes)]
        elif action.kind == "click":
            out.events.append((EV_KEY, _CLICK_CODES[action.arg], 0))

    @staticmethod
    def _repeat(sig, action: Action | None, out: Output) -> None:
        if action is None or action.kind == "key":
            codes = _ordered(sig) if action is None else list(action.arg)
            out.events.append((EV_KEY, codes[-1], 2))
        elif action.kind == "scroll":
            out.events.append((EV_REL, *_SCROLL[action.arg]))


class Learner:
    """Assistente "Aprender botões": registra assinaturas em ordem, mesa e depois caneta."""

    def __init__(self):
        self.tablet: list[Signature] = []
        self.pen: list[Signature] = []
        self.phase = "tablet"

    def next_phase(self) -> None:
        self.phase = "pen"

    def feed(self, frame: list[Event]):
        downs = frozenset(code for typ, code, value in frame if typ == EV_KEY and value == 1)
        if not downs:
            return None
        known = self.result().lookup(downs)
        if known is not None:
            return ("repeat", known)
        target = self.tablet if self.phase == "tablet" else self.pen
        target.append(downs)
        return ("added", f"{self.phase}{len(target)}")

    def result(self) -> ButtonMap:
        return ButtonMap(tuple(self.tablet), tuple(self.pen))
