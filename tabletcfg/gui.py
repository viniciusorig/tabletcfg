"""Janela de configuração da mesa."""
import dataclasses

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from . import autorule, profiles  # noqa: E402
from .apply import apply_profile, write_last  # noqa: E402
from .canvas import AreaCanvas  # noqa: E402
from .devices import find_tablet  # noqa: E402
from .identify import show_identify  # noqa: E402
from .matrix import fit_tablet_area  # noqa: E402
from .monitors import Layout, find_monitor, read_layout, resolve_target  # noqa: E402
from .proc import TabletError  # noqa: E402

FULL = (0.0, 0.0, 1.0, 1.0)
DEFAULT_MM = (160.0, 100.0)
CROP_TIP = ("Área da mesa menor que 100%: a caneta fora da área ainda move o cursor "
            "para fora do retângulo de tela (limitação do libinput).")


class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Configuração da mesa digitalizadora")
        self.set_default_size(900, 480)
        self._busy = False
        self.layout = Layout(1, 1, ())
        self.tablet = None
        self.status_msgs = []
        self.load_failed = False
        try:
            self.store = profiles.load()
        except profiles.ProfileError as e:
            self.store = profiles.Store()
            self.load_failed = True
            self.status_msgs.append(f"Erro ao ler perfis (uma cópia .bak será feita ao salvar): {e}")
        self.refresh_hardware()
        if not self.store.profiles:
            self.store.profiles["padrao"] = self._new_profile()
        self.current = self.store.saved or sorted(self.store.profiles)[0]
        self._build()
        self.reload_combo()
        self.load_profile()
        self.connect("focus-in-event", lambda *_: self._on_focus())

    # ---------- estado ----------
    @property
    def profile(self) -> profiles.Profile:
        return self.store.profiles[self.current]

    def _new_profile(self) -> profiles.Profile:
        mons = self.layout.monitors
        m = next((m for m in mons if m.primary), mons[0] if mons else None)
        if m is None:
            return profiles.Profile(target="all")
        return profiles.Profile(monitor_id=m.id, monitor_name=m.name)

    def refresh_hardware(self):
        try:
            self.layout = read_layout()
        except TabletError as e:
            self.status_msgs.append(str(e))
        try:
            self.tablet = find_tablet()
        except TabletError as e:
            self.tablet = None
            self.status_msgs.append(str(e))

    def tablet_mm(self):
        return (self.tablet.size_mm if self.tablet and self.tablet.size_mm else DEFAULT_MM)

    # ---------- construção ----------
    def _build(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, border_width=10)
        self.add(root)
        top = Gtk.Box(spacing=10)
        root.pack_start(top, True, True, 0)

        # Tela
        screen_frame = Gtk.Frame(label="Tela")
        sbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=6)
        screen_frame.add(sbox)
        self.monitor_canvas = AreaCanvas(True, self.on_monitor_change)
        self.monitor_canvas.set_tooltip_text("Clique para escolher o monitor; arraste para limitar a área")
        sbox.pack_start(self.monitor_canvas, True, True, 0)
        srow = Gtk.Box(spacing=6)
        self.all_check = Gtk.CheckButton(label="Todos os monitores")
        self.all_check.connect("toggled", self.on_all_toggled)
        full_btn = Gtk.Button(label="Área inteira")
        full_btn.connect("clicked", self.on_full_screen)
        refresh_btn = Gtk.Button(label="Atualizar")
        refresh_btn.connect("clicked", lambda *_: self._refresh_and_sync())
        ident_btn = Gtk.Button(label="Identificar")
        ident_btn.connect("clicked", lambda *_: show_identify(self.layout.monitors))
        for w in (self.all_check, full_btn, refresh_btn, ident_btn):
            srow.pack_start(w, False, False, 0)
        sbox.pack_start(srow, False, False, 0)
        top.pack_start(screen_frame, True, True, 0)

        # Mesa
        tab_frame = Gtk.Frame(label="Mesa (orientação nativa)")
        tbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=6)
        tab_frame.add(tbox)
        self.tablet_canvas = AreaCanvas(False, self.on_tablet_change)
        self.tablet_canvas.set_size_request(260, 180)
        self.tablet_canvas.set_tooltip_text(CROP_TIP)
        tbox.pack_start(self.tablet_canvas, True, True, 0)
        rrow = Gtk.Box(spacing=6)
        rrow.pack_start(Gtk.Label(label="Rotação:"), False, False, 0)
        self.rot_buttons = {}
        group = None
        for deg in (0, 90, 180, 270):
            b = Gtk.RadioButton.new_with_label_from_widget(group, f"{deg}°")
            group = group or b
            b.connect("toggled", self.on_rotation, deg)
            self.rot_buttons[deg] = b
            rrow.pack_start(b, False, False, 0)
        tbox.pack_start(rrow, False, False, 0)
        krow = Gtk.Box(spacing=6)
        self.keep_check = Gtk.CheckButton(label="Manter proporção")
        self.keep_check.connect("toggled", self.on_keep)
        tfull = Gtk.Button(label="Mesa inteira")
        tfull.connect("clicked", self.on_full_tablet)
        krow.pack_start(self.keep_check, False, False, 0)
        krow.pack_start(tfull, False, False, 0)
        tbox.pack_start(krow, False, False, 0)
        top.pack_start(tab_frame, False, False, 0)

        # Rodapé
        foot = Gtk.Box(spacing=6)
        foot.pack_start(Gtk.Label(label="Perfil:"), False, False, 0)
        self.combo = Gtk.ComboBoxText()
        self.combo.connect("changed", self.on_combo)
        foot.pack_start(self.combo, False, False, 0)
        for label, cb in (("Novo", self.on_new), ("Renomear", self.on_rename),
                          ("Excluir", self.on_delete)):
            b = Gtk.Button(label=label)
            b.connect("clicked", cb)
            foot.pack_start(b, False, False, 0)
        save_btn = Gtk.Button(label="Salvar")
        save_btn.get_style_context().add_class("suggested-action")
        save_btn.connect("clicked", self.on_save)
        test_btn = Gtk.Button(label="Testar")
        test_btn.connect("clicked", self.on_test)
        foot.pack_end(save_btn, False, False, 0)
        foot.pack_end(test_btn, False, False, 0)
        root.pack_start(foot, False, False, 0)

        self.status = Gtk.Label(xalign=0, wrap=True, selectable=True)
        root.pack_start(self.status, False, False, 0)
        self.show_status()

    # ---------- sincronização UI ⇄ perfil ----------
    def show_status(self, msgs=None):
        if msgs is not None:
            self.status_msgs = list(msgs)
        self.status.set_text("\n".join(self.status_msgs))

    def reload_combo(self):
        self._busy = True
        self.combo.remove_all()
        names = sorted(self.store.profiles)
        for n in names:
            self.combo.append_text(f"{n} ★" if n == self.store.saved else n)
        self.combo.set_active(names.index(self.current))
        self._busy = False

    def load_profile(self):
        p = self.profile
        self._busy = True
        self.all_check.set_active(p.target == "all")
        self.rot_buttons[p.rotation].set_active(True)
        self.keep_check.set_active(p.keep_aspect)
        self._busy = False
        self.sync_canvases()

    def sync_canvases(self):
        p = self.profile
        boxes = [(f"{i}: {m.name}", m.rect) for i, m in enumerate(self.layout.monitors, 1)]
        if not boxes:
            boxes = [("Desktop", self.layout.rect)]
        sel = None
        if p.target == "monitor" and self.layout.monitors:
            sel = find_monitor(self.layout, p.monitor_id, p.monitor_name)
        self.monitor_canvas.set_state(boxes, sel, p.screen_area)
        mon_rect, _ = resolve_target(self.layout, p.target, p.monitor_id, p.monitor_name)
        aspect = (p.screen_area[2] * mon_rect[2]) / (p.screen_area[3] * mon_rect[3])
        mm = self.tablet_mm()
        eff = fit_tablet_area(p.tablet_area, p.rotation, aspect, mm) if p.keep_aspect else None
        self.tablet_canvas.set_state([("Mesa", (0, 0, mm[0], mm[1]))], 0, p.tablet_area, eff)

    def _refresh_and_sync(self):
        self.status_msgs = []
        self.refresh_hardware()
        self.sync_canvases()
        self.show_status()

    def _on_focus(self):
        try:
            self.layout = read_layout()
        except TabletError:
            return False
        self.sync_canvases()
        return False

    # ---------- handlers ----------
    def on_monitor_change(self, selected, area):
        p = self.profile
        if selected is not None and self.layout.monitors:
            m = self.layout.monitors[selected]
            p.target, p.monitor_id, p.monitor_name = "monitor", m.id, m.name
            self._busy = True
            self.all_check.set_active(False)
            self._busy = False
        p.screen_area = area
        self.sync_canvases()

    def on_all_toggled(self, btn):
        if self._busy:
            return
        p = self.profile
        if btn.get_active():
            p.target = "all"
        else:
            p.target = "monitor"
            if find_monitor(self.layout, p.monitor_id, p.monitor_name) is None:
                fresh = self._new_profile()
                p.monitor_id, p.monitor_name = fresh.monitor_id, fresh.monitor_name
        p.screen_area = FULL
        self.sync_canvases()

    def on_full_screen(self, _b):
        self.profile.screen_area = FULL
        self.sync_canvases()

    def on_tablet_change(self, _sel, area):
        self.profile.tablet_area = area
        self.sync_canvases()

    def on_full_tablet(self, _b):
        self.profile.tablet_area = FULL
        self.sync_canvases()

    def on_rotation(self, btn, deg):
        if self._busy or not btn.get_active():
            return
        self.profile.rotation = deg
        self.sync_canvases()

    def on_keep(self, btn):
        if self._busy:
            return
        self.profile.keep_aspect = btn.get_active()
        self.sync_canvases()

    def on_combo(self, combo):
        if self._busy or combo.get_active() < 0:
            return
        self.current = sorted(self.store.profiles)[combo.get_active()]
        self.load_profile()

    def ask_password(self, retry: bool):
        """Pede a senha do sudo; devolve None se cancelado. A senha não é guardada."""
        d = Gtk.Dialog(title="Senha de administrador", transient_for=self, modal=True)
        d.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.OK)
        box = d.get_content_area()
        box.set_spacing(8)
        box.set_border_width(12)
        text = ("Senha incorreta, tente de novo." if retry else
                "Para reaplicar o perfil sozinho ao conectar a mesa, é preciso instalar\n"
                "uma regra do sistema (só desta vez). Digite sua senha:")
        box.add(Gtk.Label(label=text, xalign=0))
        entry = Gtk.Entry(visibility=False, activates_default=True,
                          input_purpose=Gtk.InputPurpose.PASSWORD)
        box.add(entry)
        d.show_all()
        resp = d.run()
        password = entry.get_text()
        d.destroy()
        while Gtk.events_pending():  # some o diálogo antes do sudo rodar
            Gtk.main_iteration()
        return password if resp == Gtk.ResponseType.OK and password else None

    def ask_name(self, title, initial=""):
        d = Gtk.Dialog(title=title, transient_for=self, modal=True)
        d.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.OK)
        entry = Gtk.Entry(text=initial, activates_default=True)
        d.get_content_area().add(entry)
        d.show_all()
        resp = d.run()
        name = entry.get_text().strip()
        d.destroy()
        if resp != Gtk.ResponseType.OK or not name:
            return None
        if name in self.store.profiles and name != initial:
            self.show_status([f"Já existe um perfil chamado '{name}'"])
            return None
        return name

    def on_new(self, _b):
        name = self.ask_name("Novo perfil")
        if name:
            self.store.profiles[name] = dataclasses.replace(self.profile)
            self.current = name
            self.reload_combo()
            self.load_profile()

    def on_rename(self, _b):
        name = self.ask_name("Renomear perfil", self.current)
        if name and name != self.current:
            self.store.profiles[name] = self.store.profiles.pop(self.current)
            if self.store.saved == self.current:
                self.store.saved = name
            self.current = name
            self.reload_combo()

    def on_delete(self, _b):
        if len(self.store.profiles) == 1:
            self.show_status(["Não dá para excluir o único perfil"])
            return
        del self.store.profiles[self.current]
        if self.store.saved == self.current:
            self.store.saved = None
        self.current = sorted(self.store.profiles)[0]
        self.reload_combo()
        self.load_profile()
        self.show_status(["Perfil excluído (clique em Salvar para gravar)"])

    def _apply(self):
        res = apply_profile(self.profile, self.tablet, self.layout)
        write_last(self.current)
        return res.warnings

    def on_test(self, _b):
        try:
            self.tablet = find_tablet()
            warns = self._apply()
            self.show_status([f"Perfil '{self.current}' aplicado (teste, não salvo)", *warns])
        except TabletError as e:
            self.show_status([str(e)])

    def on_save(self, _b):
        msgs = []
        self.store.saved = self.current
        try:
            if self.load_failed and (bak := profiles.backup()):
                msgs.append(f"Arquivo anterior guardado em {bak}")
            self.load_failed = False
            profiles.save(self.store)
        except (TabletError, OSError) as e:
            self.show_status([f"Não foi possível salvar: {e}"])
            return
        msgs.append(f"Perfil '{self.current}' salvo e definido como automático")
        try:
            self.tablet = find_tablet()
            msgs += self._apply()
        except TabletError as e:
            msgs.append(str(e))
        msgs += autorule.ensure_auto_apply(self.tablet, self.ask_password)
        self.reload_combo()
        self.show_status(msgs)


def run_gui() -> int:
    win = MainWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    return 0
