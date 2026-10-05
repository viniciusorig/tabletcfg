"""Geometria pura da GUI: vista mundo↔widget e retângulo de arrasto."""
from dataclasses import dataclass

from .matrix import MIN_FRAC, Rect


@dataclass(frozen=True)
class View:
    scale: float
    ox: float
    oy: float
    bx: float
    by: float

    def to_widget(self, x: float, y: float) -> tuple[float, float]:
        return (self.ox + (x - self.bx) * self.scale, self.oy + (y - self.by) * self.scale)

    def to_world(self, px: float, py: float) -> tuple[float, float]:
        return (self.bx + (px - self.ox) / self.scale, self.by + (py - self.oy) / self.scale)


def bbox(rects: list[Rect]) -> Rect:
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[0] + r[2] for r in rects)
    y1 = max(r[1] + r[3] for r in rects)
    return (x0, y0, x1 - x0, y1 - y0)


def fit_view(box: Rect, width: float, height: float, margin: float = 12) -> View:
    bx, by, bw, bh = box
    scale = max(min((width - 2 * margin) / bw, (height - 2 * margin) / bh), 1e-6)
    ox = (width - bw * scale) / 2
    oy = (height - bh * scale) / 2
    return View(scale, ox, oy, bx, by)


def point_in(rect: Rect, x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rx <= x <= rx + rw and ry <= y <= ry + rh


def rect_from_drag(p0, p1, ref: Rect, min_frac: float = MIN_FRAC) -> Rect:
    rx, ry, rw, rh = ref

    def norm(p):
        return (min(max((p[0] - rx) / rw, 0.0), 1.0), min(max((p[1] - ry) / rh, 0.0), 1.0))

    (ax, ay), (bx, by) = norm(p0), norm(p1)
    x0, x1 = sorted((ax, bx))
    y0, y1 = sorted((ay, by))
    w = max(x1 - x0, min_frac)
    h = max(y1 - y0, min_frac)
    return (min(x0, 1.0 - w), min(y0, 1.0 - h), w, h)
