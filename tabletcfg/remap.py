"""Serviço dos botões: captura o teclado da mesa e executa as ações do perfil ativo."""
import select
import signal
import subprocess
import sys
from pathlib import Path

from . import profiles
from .apply import _state_file, read_last, refresh_session
from .buttons import Action, ButtonError, ButtonMap, Remapper, devices_path, map_for, parse_action
from .proc import TabletError

POLL_SECONDS = 1.0


def actions_for(bmap: ButtonMap, store: profiles.Store,
                last: str | None) -> tuple[str | None, dict[str, Action], list[str]]:
    """Perfil ativo (último aplicado, senão o salvo) → ações dos botões que o mapa conhece."""
    name = next((n for n in (last, store.saved) if n in store.profiles), None)
    if name is None:
        return None, {}, []
    known = set(bmap.ids())
    actions, warnings = {}, []
    for button, text in store.profiles[name].buttons.items():
        if button in known:
            actions[button] = parse_action(text)
        else:
            warnings.append(f"Perfil '{name}': botão {button} não existe nesta mesa (ignorado)")
    return name, actions, warnings


class ButtonService:
    def __init__(self, bmap: ButtonMap, devices, uinput, load_config, run_command, log):
        """load_config() -> (perfil, ações, avisos); pode levantar TabletError."""
        self.devices = devices
        self.uinput = uinput
        self.load_config = load_config
        self.run_command = run_command
        self.log = log
        self.remapper = Remapper(bmap, {})
        self.grabbed = False
        self.profile = None

    def set_map(self, bmap: ButtonMap) -> None:
        self._release()
        self.remapper = Remapper(bmap, self.remapper.actions)

    def reload(self) -> None:
        try:
            name, actions, warnings = self.load_config()
        except TabletError as e:
            self.log(f"configuração não recarregada: {e}")
            return
        for w in warnings:
            self.log(w)
        self.profile = name
        self.remapper.set_actions(actions)
        want = bool(actions)
        if want != self.grabbed:
            if not want:
                self._release()
            for dev in self.devices:
                dev.grab(want)
            self.grabbed = want
            self.log(f"perfil '{name}': " + ("botões remapeados" if want else "botões originais"))

    def _release(self) -> None:
        self.uinput.emit(self.remapper.release_all().events)

    def poll(self, ready) -> bool:
        """Processa os nós prontos; False quando a mesa foi desconectada."""
        for dev in ready:
            try:
                frames = dev.read_frames()
            except OSError:
                return False
            if not self.grabbed:
                continue
            for frame in frames:
                out = self.remapper.feed(frame)
                self.uinput.emit(out.events)
                for cmd in out.commands:
                    self.run_command(cmd)
        return True

    def shutdown(self) -> None:
        self._release()
        for dev in self.devices:
            try:
                dev.grab(False)
            except OSError:
                pass


def _stamp(paths: list[Path]) -> tuple:
    out = []
    for p in paths:
        try:
            st = p.stat()
            out.append((st.st_mtime_ns, st.st_size))
        except OSError:
            out.append(None)
    return tuple(out)


class CommandRunner:
    """Roda comandos sem esperar; recolhe os que terminaram."""

    def __init__(self, log):
        self.log = log
        self.children: list[subprocess.Popen] = []

    def __call__(self, cmd: str) -> None:
        self.reap()
        refresh_session()
        try:
            self.children.append(subprocess.Popen(
                ["sh", "-c", cmd], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True))
        except OSError as e:
            self.log(f"comando falhou: {cmd}: {e}")

    def reap(self) -> None:
        self.children = [c for c in self.children if c.poll() is None]


def current_map() -> ButtonMap | None:
    """Mapa de botões da mesa conectada (None: desconectada ou modelo sem mapa)."""
    from .devices import _udev_devices, select_tablet
    tablet = select_tablet(_udev_devices(), [])
    return map_for(tablet.vendor, tablet.product) if tablet else None


def follow_buttons(log=None) -> int:
    """Processo do tabletcfg-buttons.service: vive enquanto a mesa estiver conectada."""
    from .devices import _udev_devices, button_nodes, select_tablet
    from .evdev import InputDevice, UInput

    log = log or (lambda m: print(f"tabletcfg: {m}", file=sys.stderr, flush=True))
    tablet = select_tablet(_udev_devices(), [])
    if tablet is None:
        log("mesa não conectada; nada a fazer")
        return 0
    try:
        bmap = map_for(tablet.vendor, tablet.product)
    except ButtonError as e:
        log(str(e))
        return 0
    if bmap is None:
        log("botões desta mesa desconhecidos; use 'Aprender botões' na janela")
        return 0
    nodes = button_nodes(tablet)
    if not nodes:
        log("nenhum dispositivo de botões encontrado")
        return 0

    def stop(_sig, _frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)

    def load():
        store = profiles.load()
        return actions_for(service.remapper.bmap, store, read_last())

    devices = [InputDevice(n) for n in nodes]
    uinput = UInput()
    runner = CommandRunner(log)
    service = ButtonService(bmap, devices, uinput, load, runner, log)
    watched = [profiles.default_path(), devices_path(), _state_file()]
    stamp = _stamp(watched)
    try:
        service.reload()
        while True:
            ready, _, _ = select.select(devices, [], [], POLL_SECONDS)
            if _stamp(watched) != stamp:
                stamp = _stamp(watched)
                try:
                    new_map = map_for(tablet.vendor, tablet.product)
                except ButtonError as e:
                    log(str(e))
                    new_map = None
                if new_map is not None and new_map != service.remapper.bmap:
                    service.set_map(new_map)
                service.reload()
            if not service.poll(ready):
                log("mesa desconectada")
                return 0
            runner.reap()
    finally:
        service.shutdown()
        uinput.close()
        for d in devices:
            try:
                d.close()
            except OSError:
                pass
