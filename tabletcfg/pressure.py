"""Curva de pressão da caneta: firmeza ⇄ curva, validação e geometria.

A curva do driver é uma Bézier cúbica 0/0 → (x1, y1) → (x2, y2) → 1/1; o perfil
guarda só os dois pontos de controle (x1, y1, x2, y2).
"""
import math

from .proc import TabletError

Curve = tuple[float, float, float, float]
LINEAR: Curve = (0.0, 0.0, 1.0, 1.0)
MAX_BEND = 0.8
TOL = 1e-4

# (nome na CLI, rótulo na janela, firmeza)
PRESETS = (
    ("muito-macia", "Muito macia", -1.0),
    ("macia", "Macia", -0.5),
    ("normal", "Normal", 0.0),
    ("firme", "Firme", 0.5),
    ("muito-firme", "Muito firme", 1.0),
)
CUSTOM = "Personalizada"


class PressureError(TabletError):
    pass


def curve_for_firmness(s: float) -> Curve:
    s = max(-1.0, min(1.0, float(s)))
    a = abs(s) * MAX_BEND
    if s > 0:
        return (a, 0.0, 1.0, 1.0 - a)
    if s < 0:
        return (0.0, a, 1.0 - a, 1.0)
    return LINEAR


def firmness_of(curve: Curve) -> float | None:
    """Firmeza que gera a curva, ou None se ela não pertence à família do deslizante."""
    x1, y1, x2, y2 = curve
    if abs(y1) < TOL and abs(x2 - 1) < TOL and abs(x1 - (1 - y2)) < TOL:
        return min(1.0, x1 / MAX_BEND)
    if abs(x1) < TOL and abs(y2 - 1) < TOL and abs(y1 - (1 - x2)) < TOL:
        return -min(1.0, y1 / MAX_BEND)
    return None


def preset_label(curve: Curve) -> str:
    s = firmness_of(curve)
    if s is None:
        return CUSTOM
    return min(PRESETS, key=lambda p: abs(p[2] - s))[1]


def parse_firmness(text: str) -> float:
    """Nome de predefinição ou número de -100 (macia) a 100 (firme) → -1..1."""
    key = text.strip().lower()
    for name, _, s in PRESETS:
        if key == name:
            return s
    try:
        v = float(key)
    except ValueError:
        v = math.nan
    if not (math.isfinite(v) and -100 <= v <= 100):
        names = ", ".join(p[0] for p in PRESETS)
        raise PressureError(f"Firmeza inválida '{text}': use {names} ou um número de -100 a 100")
    return v / 100


def validate_curve(curve) -> Curve:
    ok = (isinstance(curve, (list, tuple)) and len(curve) == 4
          and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                  and math.isfinite(v) and 0 <= v <= 1 for v in curve))
    if not ok or curve[0] > curve[2]:
        raise PressureError(f"Curva de pressão inválida {curve!r} (esperado [x1, y1, x2, y2] "
                            f"em 0..1 com x1 <= x2)")
    return tuple(float(v) for v in curve)


def drag_point(curve: Curve, index: int, x: float, y: float) -> Curve:
    """Move o ponto de controle index (0 ou 1) para (x, y), respeitando 0..1 e x1 <= x2."""
    x, y = max(0.0, min(1.0, x)), max(0.0, min(1.0, y))
    x1, y1, x2, y2 = curve
    if index == 0:
        return (min(x, x2), y, x2, y2)
    return (x1, y1, max(x, x1), y)


def to_prop(curve: Curve) -> list[float]:
    return [0, 0, *curve, 1, 1]


def from_prop(values: list[float]) -> Curve | None:
    if len(values) != 8:
        return None
    return tuple(float(v) for v in values[2:6])


def bezier_points(curve: Curve, steps: int = 32) -> list[tuple[float, float]]:
    x1, y1, x2, y2 = curve
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        out.append((3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3,
                    3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3))
    return out
