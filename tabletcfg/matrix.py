"""Matemática da Coordinate Transformation Matrix (CTM) do libinput. Sem I/O.

A CTM leva coordenadas normalizadas da mesa (0..1) para coordenadas
normalizadas do desktop X inteiro. Composição: M = S · R · C
(C recorta a área da mesa, R gira, S posiciona no retângulo alvo).
"""
import math

Rect = tuple[float, float, float, float]  # x, y, w, h

MIN_FRAC = 0.05
IDENTITY = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]

# Rotação da mesa no sentido horário, no quadrado unitário.
ROTATIONS = {
    0: ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    90: ((0, -1, 1), (1, 0, 0), (0, 0, 1)),
    180: ((-1, 0, 1), (0, -1, 1), (0, 0, 1)),
    270: ((0, 1, 0), (-1, 0, 1), (0, 0, 1)),
}


def _matmul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def transform(m: list[float], x: float, y: float) -> tuple[float, float]:
    return (m[0] * x + m[1] * y + m[2], m[3] * x + m[4] * y + m[5])


def fit_tablet_area(area: Rect, rotation: int, target_aspect: float,
                    tablet_mm: tuple[float, float]) -> Rect:
    """Reduz a área da mesa (centralizada) até ter o aspecto físico do alvo."""
    x, y, w, h = area
    cur = (w * tablet_mm[0]) / (h * tablet_mm[1])
    if rotation in (90, 270):
        target_aspect = 1 / target_aspect
    if math.isclose(cur, target_aspect, rel_tol=1e-9):
        return area
    if cur > target_aspect:
        nw = w * target_aspect / cur
        return (x + (w - nw) / 2, y, nw, h)
    nh = h * cur / target_aspect
    return (x, y + (h - nh) / 2, w, nh)


def build_ctm(desktop: tuple[int, int], target: Rect, tablet_area: Rect,
              rotation: int) -> list[float]:
    if rotation not in ROTATIONS:
        raise ValueError(f"rotação inválida: {rotation}")
    dw, dh = desktop
    x, y, w, h = target
    tx, ty, tw, th = tablet_area
    s = ((w / dw, 0, x / dw), (0, h / dh, y / dh), (0, 0, 1))
    c = ((1 / tw, 0, -tx / tw), (0, 1 / th, -ty / th), (0, 0, 1))
    m = _matmul(_matmul(s, ROTATIONS[rotation]), c)
    return [float(v) + 0.0 for row in m for v in row]


def compute_ctm(desktop: tuple[int, int], monitor_rect: Rect, screen_area: Rect,
                tablet_area: Rect, rotation: int, keep_aspect: bool,
                tablet_mm: tuple[float, float]) -> list[float]:
    mx, my, mw, mh = monitor_rect
    sx, sy, sw, sh = screen_area
    target = (mx + sx * mw, my + sy * mh, sw * mw, sh * mh)
    if keep_aspect:
        tablet_area = fit_tablet_area(tablet_area, rotation, target[2] / target[3], tablet_mm)
    return build_ctm(desktop, target, tablet_area, rotation)
