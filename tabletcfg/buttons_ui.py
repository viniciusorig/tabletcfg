"""Aba "Botões": ação por botão, gravação de atalho, Detectar e Aprender botões."""
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from . import autorule  # noqa: E402
from .buttons import (  # noqa: E402
    CLICKS, SCROLLS, ButtonError, ButtonMap, Learner, device_key, load_maps, map_for,
    parse_action, save_maps,
)
from .devices import button_nodes  # noqa: E402
from .evdev import EV_KEY, InputDevice  # noqa: E402
from .keys import MODIFIERS, combo_label, format_combo  # noqa: E402
from .proc import TabletError  # noqa: E402

KINDS = (("original", "Original"), ("key", "Atalho"), ("click", "Clique"),
         ("scroll", "Rolagem"), ("command", "Comando"), ("disable", "Desativar"))
DETECT_SECONDS = 10
POLL_MS = 30
ESC = 1


class ButtonCapture:
    """Lê os botões da mesa direto do evdev (pausando o serviço, que capturaria antes)."""

    def __init__(self, tablet, on_frame):
        self.on_frame = on_frame
        self.devices = []
        self.timer = None
        self.service_was_active = autorule.buttons_service_active()
        if self.service_was_active:
            autorule.stop_buttons_service()
        try:
            for node in button_nodes(tablet):
                dev = InputDevice(node)
                self.devices.append(dev)
                dev.grab()  # Tab/Espaço da mesa não mexem na janela enquanto isso
        except OSError as e:
            self.stop()
            raise TabletError(f"Não foi possível ler os botões da mesa: {e}") from None
        if not self.devices:
            self.stop()
            raise TabletError("Nenhum dispositivo de botões encontrado")
        self.timer = GLib.timeout_add(POLL_MS, self._poll)

    def _poll(self):
        for dev in self.devices:
            try:
                frames = dev.read_frames()
            except OSError:
                frames = []
            for frame in frames:
                if self.timer is None:
                    return False
                self.on_frame(frame)
        return self.timer is not None

    def stop(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        for dev in self.devices:
            try:
                dev.close()
            except OSError:
                pass
        self.devices = []
        if self.service_was_active:
            self.service_was_active = False
            try:
                autorule.start_buttons_service()
            except TabletError:
                pass


def record_shortcut(parent) -> tuple[int, ...] | None:
    """Diálogo que grava a próxima combinação do teclado (códigos evdev; X = evdev + 8)."""
    d = Gtk.Dialog(title="Gravar atalho", transient_for=parent, modal=True)
    d.add_button("Cancelar", Gtk.ResponseType.CANCEL)
    label = Gtk.Label(label="Aperte a combinação de teclas…\n(Esc cancela)", margin=16)
    d.get_content_area().add(label)
    pressed: list[int] = []
    result: list[tuple[int, ...]] = []

    def finish(codes):
        result.append(tuple(codes))
        d.response(Gtk.ResponseType.OK)

    def on_press(_w, ev):
        code = ev.hardware_keycode - 8
        if code == ESC and not pressed:
            d.response(Gtk.ResponseType.CANCEL)
            return True
        if code not in pressed:
            pressed.append(code)
        if code not in MODIFIERS:
            finish(pressed)
        else:
            label.set_text(combo_label(pressed) + "+…")
        return True

    def on_release(_w, ev):
        if pressed and all(c in MODIFIERS for c in pressed):
            finish(pressed)  # combinação só de modificadores (ex.: Ctrl)
        return True

    d.connect("key-press-event", on_press)
    d.connect("key-release-event", on_release)
    d.show_all()
    resp = d.run()
    d.destroy()
    return result[0] if resp == Gtk.ResponseType.OK and result else None


class ButtonRow:
    def __init__(self, page, grid, row, button, signature):
        self.page = page
        self.button = button
        self.name = Gtk.Label(label=ButtonMap.label(button), xalign=0)
        sends = Gtk.Label(label=combo_label(signature), xalign=0)
        self.kind = Gtk.ComboBoxText()
        for key, text in KINDS:
            self.kind.append(key, text)
        self.kind.connect("changed", self._on_kind)
        self.stack = Gtk.Stack(hhomogeneous=False)
        self.stack.add_named(Gtk.Label(), "original")
        self.stack.add_named(Gtk.Label(), "disable")
        kbox = Gtk.Box(spacing=6)
        self.combo_label = Gtk.Label(label="(nenhum)", xalign=0, width_chars=14)
        rec = Gtk.Button(label="Gravar")
        rec.connect("clicked", self._on_record)
        kbox.pack_start(self.combo_label, False, False, 0)
        kbox.pack_start(rec, False, False, 0)
        self.stack.add_named(kbox, "key")
        self.click = Gtk.ComboBoxText()
        for key, text in CLICKS.items():
            self.click.append(key, text.capitalize())
        self.click.connect("changed", lambda *_: self._store())
        self.stack.add_named(self.click, "click")
        self.scroll = Gtk.ComboBoxText()
        for key, text in SCROLLS.items():
            self.scroll.append(key, text.capitalize())
        self.scroll.connect("changed", lambda *_: self._store())
        self.stack.add_named(self.scroll, "scroll")
        self.command = Gtk.Entry(placeholder_text="ex.: tabletcfg next", width_chars=24)
        self.command.connect("changed", lambda *_: self._store())
        self.stack.add_named(self.command, "command")
        self.codes: tuple[int, ...] = ()
        for col, w in enumerate((self.name, sends, self.kind, self.stack)):
            grid.attach(w, col, row, 1, 1)

    def set_action(self, text: str | None):
        self.page.busy = True
        try:
            action = parse_action(text) if text else None
        except ButtonError:
            action = None
        kind = action.kind if action else "original"
        self.kind.set_active_id(kind)
        self.stack.set_visible_child_name(kind)
        self.codes = action.arg if kind == "key" else ()
        self.combo_label.set_text(combo_label(self.codes) if self.codes else "(nenhum)")
        self.click.set_active_id(action.arg if kind == "click" else "left")
        self.scroll.set_active_id(action.arg if kind == "scroll" else "down")
        self.command.set_text(action.arg if kind == "command" else "")
        self.page.busy = False

    def highlight(self, on: bool):
        text = ButtonMap.label(self.button)
        self.name.set_markup(f"<b>▶ {text}</b>" if on else GLib.markup_escape_text(text))

    def _on_kind(self, combo):
        kind = combo.get_active_id()
        self.stack.set_visible_child_name(kind)
        if not self.page.busy and kind == "key" and not self.codes:
            self._on_record(None)
        self._store()

    def _on_record(self, _b):
        codes = record_shortcut(self.page.get_toplevel())
        if codes:
            self.codes = codes
            self.combo_label.set_text(combo_label(codes))
        self._store()

    def action_text(self) -> str | None:
        kind = self.kind.get_active_id()
        if kind == "key":
            return f"key {format_combo(self.codes)}" if self.codes else None
        if kind == "click":
            return f"click {self.click.get_active_id()}"
        if kind == "scroll":
            return f"scroll {self.scroll.get_active_id()}"
        if kind == "command":
            cmd = self.command.get_text().strip()
            return f"command {cmd}" if cmd else None
        if kind == "disable":
            return "disable"
        return None

    def _store(self):
        if not self.page.busy:
            self.page.on_change(self.button, self.action_text())


class ButtonsPage(Gtk.Box):
    """on_change(botão, ação_em_texto | None) a cada mudança do usuário."""

    def __init__(self, on_change, show_status):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, border_width=8)
        self.on_change = on_change
        self.show_status = show_status
        self.busy = False
        self.tablet = None
        self.bmap = None
        self.rows: dict[str, ButtonRow] = {}
        self.capture = None
        self.profile_buttons: dict[str, str] = {}

        top = Gtk.Box(spacing=6)
        self.detect_btn = Gtk.Button(label="Detectar")
        self.detect_btn.set_tooltip_text("Aperte um botão da mesa ou da caneta para achar a linha")
        self.detect_btn.connect("clicked", self.on_detect)
        self.learn_btn = Gtk.Button(label="Aprender botões")
        self.learn_btn.connect("clicked", self.on_learn)
        self.info = Gtk.Label(xalign=0)
        top.pack_start(self.detect_btn, False, False, 0)
        top.pack_start(self.learn_btn, False, False, 0)
        top.pack_start(self.info, True, True, 6)
        self.pack_start(top, False, False, 0)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        self.grid = Gtk.Grid(column_spacing=12, row_spacing=6, border_width=4)
        scroller.add(self.grid)
        self.pack_start(scroller, True, True, 0)
        self.service = Gtk.Label(xalign=0)
        self.pack_start(self.service, False, False, 0)
        self.connect("destroy", lambda *_: self._stop_capture())

    # ---------- estado ----------
    def set_tablet(self, tablet):
        self.tablet = tablet
        try:
            self.bmap = map_for(tablet.vendor, tablet.product) if tablet else None
        except ButtonError as e:
            self.bmap = None
            self.show_status([str(e)])
        self._build_rows()
        self.refresh_service()

    def set_profile(self, buttons: dict[str, str]):
        self.profile_buttons = buttons
        for button, row in self.rows.items():
            row.set_action(buttons.get(button))

    def refresh_service(self):
        try:
            active = autorule.buttons_service_active()
        except TabletError:
            active = False
        self.service.set_text("Serviço dos botões: " + ("ativo" if active else "parado")
                              + " — as mudanças valem ao clicar em Salvar")

    def _build_rows(self):
        for child in self.grid.get_children():
            self.grid.remove(child)
        self.rows = {}
        if self.tablet is None:
            self.info.set_text("Mesa não conectada")
        elif self.bmap is None:
            self.info.set_text("Botões desta mesa ainda não conhecidos: use 'Aprender botões'")
        else:
            self.info.set_text(f"{self.tablet.name} — {len(self.bmap.tablet)} botões na mesa, "
                               f"{len(self.bmap.pen)} na caneta")
        self.detect_btn.set_sensitive(self.bmap is not None)
        self.learn_btn.set_sensitive(self.tablet is not None)
        if self.bmap is None:
            return
        for col, text in enumerate(("Botão", "Envia hoje", "Ação", "")):
            lbl = Gtk.Label(xalign=0)
            lbl.set_markup(f"<b>{text}</b>")
            self.grid.attach(lbl, col, 0, 1, 1)
        for i, button in enumerate(self.bmap.ids(), 1):
            self.rows[button] = ButtonRow(self, self.grid, i, button, self.bmap.signature(button))
        self.grid.show_all()
        self.set_profile(self.profile_buttons)

    # ---------- Detectar ----------
    def _stop_capture(self):
        if self.capture is not None:
            self.capture.stop()
            self.capture = None

    def _modal(self, title, text):
        d = Gtk.Dialog(title=title, transient_for=self.get_toplevel(), modal=True)
        lbl = Gtk.Label(label=text, margin=16, xalign=0)
        d.get_content_area().add(lbl)
        return d, lbl

    def on_detect(self, _b):
        d, _ = self._modal("Detectar botão", "Aperte um botão da mesa ou da caneta…\n"
                           "(a caneta precisa estar perto da mesa)")
        d.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        found = []

        def on_frame(frame):
            downs = frozenset(c for t, c, v in frame if t == EV_KEY and v == 1)
            if downs and not found:
                found.append(self.bmap.lookup(downs) or "")
                d.response(Gtk.ResponseType.OK)

        try:
            self.capture = ButtonCapture(self.tablet, on_frame)
        except TabletError as e:
            d.destroy()
            self.show_status([str(e)])
            return
        timer = [None]

        def give_up():
            timer[0] = None
            d.response(Gtk.ResponseType.CANCEL)
            return False

        timer[0] = GLib.timeout_add_seconds(DETECT_SECONDS, give_up)
        d.show_all()
        d.run()
        if timer[0] is not None:
            GLib.source_remove(timer[0])
        d.destroy()
        self._stop_capture()
        if found and found[0] in self.rows:
            for b, row in self.rows.items():
                row.highlight(b == found[0])
            self.rows[found[0]].kind.grab_focus()
            self.show_status([f"{ButtonMap.label(found[0])} detectado"])
        elif found:
            self.show_status(["Esse botão não está no mapa desta mesa; use 'Aprender botões'"])

    # ---------- Aprender ----------
    def on_learn(self, _b):
        learner = Learner()
        d, step = self._modal("Aprender botões", "")
        lines = Gtk.Label(xalign=0, margin=8)
        d.get_content_area().add(lines)
        next_btn = d.add_button("Próximo", 1)
        d.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        texts = []

        def show_step():
            if learner.phase == "tablet":
                step.set_text("1/2 — Aperte os botões da MESA, um de cada vez, em ordem física.\n"
                              "Clique em Próximo quando acabar.")
            else:
                step.set_text("2/2 — Aproxime a caneta e aperte os botões dela, do mais perto da\n"
                              "ponta para cima (se não tiver botões, só clique em Concluir).")
                next_btn.set_label("Concluir")
            lines.set_text("\n".join(texts[-12:]) or "(nenhum botão registrado ainda)")

        def on_frame(frame):
            res = learner.feed(frame)
            if res is None:
                return
            kind, button = res
            sig = learner.result().signature(button)
            if kind == "added":
                texts.append(f"{ButtonMap.label(button)}: {combo_label(sig)}")
            else:
                texts.append(f"(já registrado como {ButtonMap.label(button)}: ignorado)")
            show_step()

        try:
            self.capture = ButtonCapture(self.tablet, on_frame)
        except TabletError as e:
            d.destroy()
            self.show_status([str(e)])
            return
        show_step()
        d.show_all()
        result = None
        while True:
            resp = d.run()
            if resp == 1 and learner.phase == "tablet":
                learner.next_phase()
                texts.append("— caneta —")
                show_step()
                continue
            if resp == 1:
                result = learner.result()
            break
        d.destroy()
        self._stop_capture()
        if result is None:
            return
        if not result.tablet and not result.pen:
            self.show_status(["Nenhum botão registrado; mapa não alterado"])
            return
        try:
            maps = load_maps()
            maps[device_key(self.tablet.vendor, self.tablet.product)] = result
            save_maps(maps)
        except (ButtonError, OSError) as e:
            self.show_status([f"Não foi possível gravar o mapa: {e}"])
            return
        self.show_status([f"Mapa gravado: {len(result.tablet)} botões na mesa, "
                          f"{len(result.pen)} na caneta"])
        self.set_tablet(self.tablet)
