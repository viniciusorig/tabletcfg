"""Nomes de teclas (códigos evdev) e combinações como "ctrl+shift+s"."""
from .proc import TabletError


class ComboError(TabletError):
    pass


# nome canônico → código evdev (linux/input-event-codes.h)
_CODES = {
    "esc": 1, "minus": 12, "equal": 13, "backspace": 14, "tab": 15,
    "bracketleft": 26, "bracketright": 27, "enter": 28, "leftctrl": 29,
    "semicolon": 39, "apostrophe": 40, "grave": 41, "leftshift": 42, "backslash": 43,
    "comma": 51, "period": 52, "slash": 53, "rightshift": 54, "kp_multiply": 55,
    "leftalt": 56, "space": 57, "capslock": 58, "numlock": 69, "scrolllock": 70,
    "kp_subtract": 74, "kp_add": 78, "kp_decimal": 83, "less": 86, "ro": 89,
    "kp_enter": 96, "rightctrl": 97, "kp_divide": 98, "print": 99, "rightalt": 100,
    "home": 102, "up": 103, "pageup": 104, "left": 105, "right": 106, "end": 107,
    "down": 108, "pagedown": 109, "insert": 110, "delete": 111, "pause": 119,
    "leftmeta": 125, "rightmeta": 126, "menu": 127,
}
for _i, _c in enumerate("1234567890"):
    _CODES[_c] = 2 + _i
for _row, _start in (("qwertyuiop", 16), ("asdfghjkl", 30), ("zxcvbnm", 44)):
    for _i, _c in enumerate(_row):
        _CODES[_c] = _start + _i
for _i in range(10):
    _CODES[f"f{_i + 1}"] = 59 + _i
_CODES["f11"], _CODES["f12"] = 87, 88
for _i, _c in enumerate((79, 80, 81, 75, 76, 77, 71, 72, 73)):
    _CODES[f"kp{_i + 1}"] = _c
_CODES["kp0"] = 82

_NAMES = {c: n for n, c in _CODES.items()}

_ALIASES = {
    "ctrl": "leftctrl", "control": "leftctrl", "shift": "leftshift", "alt": "leftalt",
    "altgr": "rightalt", "super": "leftmeta", "win": "leftmeta", "meta": "leftmeta",
    "rctrl": "rightctrl", "rshift": "rightshift", "return": "enter", "escape": "esc",
    "del": "delete", "[": "bracketleft", "]": "bracketright", "-": "minus", "=": "equal",
    ";": "semicolon", "'": "apostrophe", "`": "grave", "\\": "backslash", ",": "comma",
    ".": "period", "/": "slash", "leftbrace": "bracketleft", "rightbrace": "bracketright",
    "kpplus": "kp_add", "kpminus": "kp_subtract",
}

# ordem canônica dos modificadores numa combinação
_MOD_ORDER = ("leftctrl", "rightctrl", "leftshift", "rightshift", "leftalt", "rightalt",
              "leftmeta", "rightmeta")
MODIFIERS = frozenset(_CODES[n] for n in _MOD_ORDER)
# como os modificadores aparecem no texto canônico ("ctrl" em vez de "leftctrl")
_SHORT = {"leftctrl": "ctrl", "leftshift": "shift", "leftalt": "alt", "rightalt": "altgr",
          "leftmeta": "super", "rightctrl": "rctrl", "rightshift": "rshift",
          "rightmeta": "rightmeta"}

_LABELS = {
    "leftctrl": "Ctrl", "rightctrl": "Ctrl dir.", "leftshift": "Shift",
    "rightshift": "Shift dir.", "leftalt": "Alt", "rightalt": "AltGr", "leftmeta": "Super",
    "rightmeta": "Super dir.", "space": "Espaço", "tab": "Tab", "enter": "Enter",
    "esc": "Esc", "backspace": "Backspace", "delete": "Delete", "insert": "Insert",
    "kp_add": "KP +", "kp_subtract": "KP −", "kp_multiply": "KP *", "kp_divide": "KP /",
    "kp_enter": "KP Enter", "kp_decimal": "KP ,", "bracketleft": "[", "bracketright": "]",
    "minus": "-", "equal": "=", "semicolon": ";", "apostrophe": "'", "grave": "`",
    "backslash": "\\", "comma": ",", "period": ".", "slash": "/", "up": "↑", "down": "↓",
    "left": "←", "right": "→", "pageup": "PgUp", "pagedown": "PgDn", "home": "Home",
    "end": "End",
}


def name_of(code: int) -> str:
    return _NAMES.get(code, f"code{code}")


def code_of(name: str) -> int:
    key = name.strip()
    key = _ALIASES.get(key, key.lower())
    key = _ALIASES.get(key, key)
    if key in _CODES:
        return _CODES[key]
    if key.startswith("code") and key[4:].isdigit():
        return int(key[4:])
    raise ComboError(f"Tecla desconhecida '{name}'")


def _sorted(codes) -> tuple[int, ...]:
    order = {_CODES[n]: i for i, n in enumerate(_MOD_ORDER)}
    return tuple(sorted(dict.fromkeys(codes), key=lambda c: (order.get(c, 99), c)))


def parse_combo(text: str) -> tuple[int, ...]:
    """'ctrl+shift+s' → códigos (modificadores primeiro). No máximo uma tecla comum."""
    parts = text.split("+")  # "ctrl++" fica inválido: use kp_add ou equal
    if any(not p.strip() for p in parts):
        raise ComboError(f"Atalho inválido '{text}'")
    codes = [code_of(p) for p in parts]
    if sum(c not in MODIFIERS for c in codes) > 1:
        raise ComboError(f"Atalho inválido '{text}': só uma tecla além dos modificadores")
    return _sorted(codes)


def format_combo(codes) -> str:
    out = []
    for c in _sorted(codes):
        n = name_of(c)
        out.append(_SHORT.get(n, n))
    return "+".join(out)


def combo_label(codes) -> str:
    out = []
    for c in _sorted(codes):
        n = name_of(c)
        out.append(_LABELS.get(n, n.upper() if len(n) == 1 else n.capitalize()))
    return "+".join(out)
