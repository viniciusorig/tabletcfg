"""Botões da mesa: ações por botão, mapa de botões por modelo e remapeamento (puro)."""
from dataclasses import dataclass

from .keys import ComboError, combo_label, format_combo, parse_combo
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
