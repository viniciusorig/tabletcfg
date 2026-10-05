"""Mostra número + nome grandes no centro de cada monitor."""
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402


def show_identify(monitors, seconds: float = 2.0, standalone: bool = False) -> None:
    windows = []
    for i, m in enumerate(monitors, 1):
        win = Gtk.Window(type=Gtk.WindowType.POPUP)
        label = Gtk.Label()
        label.set_markup(f'<span size="72000" weight="bold">{i}</span>\n'
                         f'<span size="24000">{GLib.markup_escape_text(m.name)}</span>')
        label.set_justify(Gtk.Justification.CENTER)
        win.add(label)
        win.set_border_width(32)
        win.show_all()
        w, h = win.get_size()
        win.move(m.x + (m.w - w) // 2, m.y + (m.h - h) // 2)
        windows.append(win)

    def close():
        for win in windows:
            win.destroy()
        if standalone:
            Gtk.main_quit()
        return False

    GLib.timeout_add(int(seconds * 1000), close)
    if standalone:
        Gtk.main()
