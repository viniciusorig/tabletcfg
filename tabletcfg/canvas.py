"""Widget que desenha caixas (monitores ou a mesa) e deixa escolher/arrastar uma área."""
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from .geometry import bbox, fit_view, point_in, rect_from_drag  # noqa: E402

DRAG_THRESHOLD = 4


class AreaCanvas(Gtk.DrawingArea):
    def __init__(self, selectable: bool, on_change):
        super().__init__()
        self.selectable = selectable
        self.on_change = on_change
        self.boxes = []          # [(rótulo, Rect mundo)]
        self.selected = None     # índice ou None (= todas as caixas)
        self.area = (0.0, 0.0, 1.0, 1.0)
        self.effective = None    # área efetiva (tracejada), em frações da referência
        self._press = None
        self._dragging = False
        self.set_size_request(320, 200)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.BUTTON1_MOTION_MASK)
        self.connect("button-press-event", self._on_press)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("button-release-event", self._on_release)

    def set_state(self, boxes, selected, area, effective=None):
        self.boxes, self.selected, self.area, self.effective = boxes, selected, area, effective
        self.queue_draw()

    def _ref(self):
        if self.selected is None:
            return bbox([r for _, r in self.boxes])
        return self.boxes[self.selected][1]

    def _view(self):
        return fit_view(bbox([r for _, r in self.boxes]),
                        self.get_allocated_width(), self.get_allocated_height())

    @staticmethod
    def _frac_to_world(ref, frac):
        rx, ry, rw, rh = ref
        fx, fy, fw, fh = frac
        return (rx + fx * rw, ry + fy * rh, fw * rw, fh * rh)

    def _rect_path(self, cr, view, rect):
        x0, y0 = view.to_widget(rect[0], rect[1])
        x1, y1 = view.to_widget(rect[0] + rect[2], rect[1] + rect[3])
        cr.rectangle(x0, y0, x1 - x0, y1 - y0)

    def do_draw(self, cr):
        if not self.boxes:
            return False
        view = self._view()
        for i, (label, rect) in enumerate(self.boxes):
            active = self.selected is None or self.selected == i
            cr.set_source_rgb(*((0.30, 0.33, 0.38) if active else (0.20, 0.21, 0.23)))
            self._rect_path(cr, view, rect)
            cr.fill_preserve()
            cr.set_source_rgb(*((0.55, 0.75, 1.0) if active else (0.45, 0.45, 0.48)))
            cr.set_line_width(2)
            cr.stroke()
            cx, cy = view.to_widget(rect[0] + rect[2] / 2, rect[1] + rect[3] / 2)
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.set_font_size(14)
            ext = cr.text_extents(label)
            cr.move_to(cx - ext.width / 2, cy + ext.height / 2)
            cr.show_text(label)
        ref = self._ref()
        self._rect_path(cr, view, self._frac_to_world(ref, self.area))
        cr.set_source_rgba(1.0, 0.6, 0.2, 0.35)
        cr.fill_preserve()
        cr.set_source_rgb(1.0, 0.6, 0.2)
        cr.set_line_width(2)
        cr.stroke()
        if self.effective is not None:
            self._rect_path(cr, view, self._frac_to_world(ref, self.effective))
            cr.set_source_rgb(1.0, 1.0, 1.0)
            cr.set_dash([5, 4])
            cr.set_line_width(1.5)
            cr.stroke()
            cr.set_dash([])
        return False

    def _on_press(self, _w, ev):
        if ev.button == 1 and self.boxes:
            self._press = self._view().to_world(ev.x, ev.y)
            self._dragging = False
        return True

    def _on_motion(self, _w, ev):
        if self._press is None:
            return True
        view = self._view()
        px, py = view.to_widget(*self._press)
        if not self._dragging and abs(ev.x - px) + abs(ev.y - py) < DRAG_THRESHOLD:
            return True
        self._dragging = True
        self.area = rect_from_drag(self._press, view.to_world(ev.x, ev.y), self._ref())
        self.queue_draw()
        return True

    def _on_release(self, _w, ev):
        if self._press is None:
            return True
        start, self._press = self._press, None
        if self._dragging:
            self._dragging = False
            self.on_change(self.selected, self.area)
            return True
        if self.selectable:
            for i, (_, rect) in enumerate(self.boxes):
                if point_in(rect, *start) and i != self.selected:
                    self.selected = i
                    self.area = (0.0, 0.0, 1.0, 1.0)
                    self.on_change(i, self.area)
                    break
        return True
