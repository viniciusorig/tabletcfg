"""Aba "Pressão": deslizante de firmeza, editor da curva e área de teste."""
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from . import pressure  # noqa: E402

MARGIN = 12
HANDLE_R = 6


class CurveEditor(Gtk.DrawingArea):
    """Quadrado 0..1 com a curva; os dois pontos de controle se arrastam."""

    def __init__(self, on_change):
        super().__init__()
        self.on_change = on_change
        self.curve = pressure.LINEAR
        self._drag = None
        self.set_size_request(220, 220)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.BUTTON1_MOTION_MASK)
        self.connect("button-press-event", self._on_press)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("button-release-event", self._on_release)

    def set_curve(self, curve):
        self.curve = curve
        self.queue_draw()

    def _box(self):
        side = min(self.get_allocated_width(), self.get_allocated_height()) - 2 * MARGIN
        return MARGIN, MARGIN, max(side, 1)

    def _to_widget(self, x, y):
        ox, oy, side = self._box()
        return ox + x * side, oy + (1 - y) * side

    def _to_unit(self, wx, wy):
        ox, oy, side = self._box()
        return (wx - ox) / side, 1 - (wy - oy) / side

    def do_draw(self, cr):
        ox, oy, side = self._box()
        cr.set_source_rgb(0.20, 0.21, 0.23)
        cr.rectangle(ox, oy, side, side)
        cr.fill()
        cr.set_source_rgb(0.45, 0.45, 0.48)
        cr.set_line_width(1)
        cr.set_dash([5, 4])
        cr.move_to(*self._to_widget(0, 0))
        cr.line_to(*self._to_widget(1, 1))
        cr.stroke()
        cr.set_dash([])
        x1, y1, x2, y2 = self.curve
        cr.set_source_rgb(0.55, 0.55, 0.6)
        for a, b in (((0, 0), (x1, y1)), ((1, 1), (x2, y2))):
            cr.move_to(*self._to_widget(*a))
            cr.line_to(*self._to_widget(*b))
            cr.stroke()
        cr.set_source_rgb(0.55, 0.75, 1.0)
        cr.set_line_width(2.5)
        pts = pressure.bezier_points(self.curve, 48)
        cr.move_to(*self._to_widget(*pts[0]))
        for p in pts[1:]:
            cr.line_to(*self._to_widget(*p))
        cr.stroke()
        cr.set_source_rgb(1.0, 0.6, 0.2)
        for x, y in ((x1, y1), (x2, y2)):
            wx, wy = self._to_widget(x, y)
            cr.arc(wx, wy, HANDLE_R, 0, 6.2832)
            cr.fill()
        cr.set_source_rgb(0.75, 0.75, 0.75)
        cr.set_font_size(11)
        cr.move_to(ox + side - cr.text_extents("força").x_advance - 4, oy + side - 4)
        cr.show_text("força")
        cr.move_to(ox + 4, oy + 14)
        cr.show_text("traço")
        return False

    def _on_press(self, _w, ev):
        if ev.button == 1:
            x, y = self._to_unit(ev.x, ev.y)
            self._drag = pressure.nearest_point(self.curve, x, y)
            self._move(ev)
        return True

    def _on_motion(self, _w, ev):
        if self._drag is not None:
            self._move(ev)
        return True

    def _on_release(self, _w, _ev):
        self._drag = None
        return True

    def _move(self, ev):
        self.curve = pressure.drag_point(self.curve, self._drag, *self._to_unit(ev.x, ev.y))
        self.queue_draw()
        self.on_change(self.curve)


class PressureTest(Gtk.DrawingArea):
    """Área de desenho: espessura do traço proporcional à pressão recebida."""

    def __init__(self, on_pressure):
        super().__init__()
        self.on_pressure = on_pressure
        self.strokes = []
        self.set_size_request(200, 200)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.BUTTON1_MOTION_MASK)
        self.connect("button-press-event", self._on_press)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("button-release-event", self._on_release)

    def clear(self):
        self.strokes = []
        self.queue_draw()

    @staticmethod
    def _pressure(ev):
        return pressure.axis_pressure(ev.get_axis(Gdk.AxisUse.PRESSURE))

    def _add(self, ev):
        p = self._pressure(ev)
        self.strokes[-1].append((ev.x, ev.y, p))
        self.on_pressure(p)
        self.queue_draw()

    def _on_press(self, _w, ev):
        if ev.button == 1:
            self.strokes.append([])
            self._add(ev)
        return True

    def _on_motion(self, _w, ev):
        if self.strokes:
            self._add(ev)
        return True

    def _on_release(self, _w, _ev):
        self.on_pressure(0.0)
        return True

    def do_draw(self, cr):
        cr.set_source_rgb(0.97, 0.97, 0.95)
        cr.paint()
        cr.set_source_rgb(0.1, 0.1, 0.12)
        cr.set_line_cap(1)  # redondo
        for stroke in self.strokes:
            for (xa, ya, _), (xb, yb, p) in zip(stroke, stroke[1:]):
                cr.set_line_width(1 + 14 * p if p is not None else 1)
                cr.move_to(xa, ya)
                cr.line_to(xb, yb)
                cr.stroke()
        return False


class PressurePage(Gtk.Box):
    """Conteúdo da aba. on_change(curve) é chamado a cada mudança feita pelo usuário."""

    def __init__(self, on_change):
        super().__init__(spacing=12, border_width=8)
        self.on_change = on_change
        self._busy = False

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        row = Gtk.Box(spacing=6)
        row.pack_start(Gtk.Label(label="Macia"), False, False, 0)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -100, 100, 1)
        self.scale.set_draw_value(False)
        self.scale.set_size_request(240, -1)
        for _, _, s in pressure.PRESETS:
            self.scale.add_mark(s * 100, Gtk.PositionType.BOTTOM, None)
        self.scale.connect("value-changed", self._on_scale)
        row.pack_start(self.scale, True, True, 0)
        row.pack_start(Gtk.Label(label="Firme"), False, False, 0)
        left.pack_start(row, False, False, 0)
        self.label = Gtk.Label(xalign=0)
        left.pack_start(self.label, False, False, 0)
        self.editor = CurveEditor(self._on_editor)
        expander = Gtk.Expander(label="Avançado")
        expander.add(self.editor)
        left.pack_start(expander, False, False, 0)
        self.pack_start(left, False, False, 0)

        test_frame = Gtk.Frame(label="Teste (desenhe com a caneta)")
        tbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=6)
        test_frame.add(tbox)
        self.test = PressureTest(self._on_pressure)
        tbox.pack_start(self.test, True, True, 0)
        brow = Gtk.Box(spacing=6)
        brow.pack_start(Gtk.Label(label="Pressão:"), False, False, 0)
        self.level = Gtk.LevelBar()
        self.level.set_size_request(80, -1)
        brow.pack_start(self.level, True, True, 0)
        self.level_text = Gtk.Label(label="0%", width_chars=12, xalign=0)
        brow.pack_start(self.level_text, False, False, 0)
        clear = Gtk.Button(label="Limpar")
        clear.connect("clicked", lambda *_: self.test.clear())
        brow.pack_start(clear, False, False, 0)
        tbox.pack_start(brow, False, False, 0)
        self.pack_start(test_frame, True, True, 0)

    def set_curve(self, curve):
        self._busy = True
        s = pressure.firmness_of(curve)
        if s is not None:
            self.scale.set_value(s * 100)
        self._busy = False
        self.editor.set_curve(curve)
        self.label.set_text(pressure.preset_label(curve))

    def _on_scale(self, scale):
        if self._busy:
            return
        curve = pressure.curve_for_firmness(scale.get_value() / 100)
        self.editor.set_curve(curve)
        self.label.set_text(pressure.preset_label(curve))
        self.on_change(curve)

    def _on_editor(self, curve):
        self.label.set_text(pressure.preset_label(curve))
        self.on_change(curve)

    def _on_pressure(self, p):
        self.level.set_value(p or 0.0)
        self.level_text.set_text("sem pressão" if p is None else f"{round(p * 100)}%")
