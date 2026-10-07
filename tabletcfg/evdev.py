"""Acesso de baixo nível ao evdev e ao uinput (só biblioteca padrão)."""
import fcntl
import os
import struct

# linux/input-event-codes.h
EV_SYN, EV_KEY, EV_REL, EV_MSC = 0x00, 0x01, 0x02, 0x04
SYN_REPORT, SYN_DROPPED = 0, 3
BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112
REL_X, REL_Y, REL_HWHEEL, REL_WHEEL = 0x00, 0x01, 0x06, 0x08
BUS_USB = 0x03

EVENT_FMT = "llHHi"  # struct input_event (timeval de 64 bits)
EVENT_SIZE = struct.calcsize(EVENT_FMT)


def _IOW(kind: str, nr: int, size: int) -> int:
    return (1 << 30) | (size << 16) | (ord(kind) << 8) | nr


def _IO(kind: str, nr: int) -> int:
    return (ord(kind) << 8) | nr


EVIOCGRAB = _IOW("E", 0x90, 4)
UI_SET_EVBIT = _IOW("U", 100, 4)
UI_SET_KEYBIT = _IOW("U", 101, 4)
UI_SET_RELBIT = _IOW("U", 102, 4)
UI_DEV_CREATE = _IO("U", 1)
UI_DEV_DESTROY = _IO("U", 2)

Event = tuple[int, int, int]


def pack_event(typ: int, code: int, value: int) -> bytes:
    return struct.pack(EVENT_FMT, 0, 0, typ, code, value)


def unpack_events(data: bytes) -> list[Event]:
    return [struct.unpack_from(EVENT_FMT, data, i)[2:]
            for i in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE)]


def uinput_user_dev(name: str, vendor: int, product: int) -> bytes:
    """struct uinput_user_dev (interface antiga do uinput, suficiente para teclas e REL)."""
    head = struct.pack("80sHHHHi", name.encode()[:79], BUS_USB, vendor, product, 1, 0)
    return head + bytes(4 * 64 * 4)


class FrameReader:
    """Agrupa eventos em pacotes (até SYN_REPORT), sem os eventos SYN."""

    def __init__(self):
        self._frame: list[Event] = []

    def feed(self, events: list[Event]) -> list[list[Event]]:
        frames = []
        for ev in events:
            if ev[0] == EV_SYN:
                if ev[1] == SYN_REPORT and self._frame:
                    frames.append(self._frame)
                self._frame = []
            else:
                self._frame.append(ev)
        return frames


class InputDevice:
    """Nó /dev/input/eventN aberto para leitura (com captura exclusiva opcional)."""

    def __init__(self, path: str):
        self.path = path
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        self.reader = FrameReader()
        self.grabbed = False

    def fileno(self) -> int:
        return self.fd

    def grab(self, on: bool = True) -> None:
        if on != self.grabbed:
            fcntl.ioctl(self.fd, EVIOCGRAB, 1 if on else 0)
            self.grabbed = on

    def read_frames(self) -> list[list[Event]]:
        """Pacotes completos disponíveis; OSError (ENODEV) quando a mesa sai."""
        try:
            data = os.read(self.fd, EVENT_SIZE * 64)
        except BlockingIOError:
            return []
        return self.reader.feed(unpack_events(data))

    def close(self) -> None:
        try:
            if self.grabbed:
                self.grab(False)
        except OSError:
            pass
        os.close(self.fd)


class UInput:
    """Teclado + mouse virtual por onde saem as ações."""

    def __init__(self, name: str = "tabletcfg botões", vendor: int = 0x1209, product: int = 0x7ab1):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_REL)
            for code in list(range(1, 256)) + [BTN_LEFT, BTN_RIGHT, BTN_MIDDLE]:
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            for code in (REL_X, REL_Y, REL_HWHEEL, REL_WHEEL):
                fcntl.ioctl(self.fd, UI_SET_RELBIT, code)
            os.write(self.fd, uinput_user_dev(name, vendor, product))
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except BaseException:
            os.close(self.fd)
            raise

    def emit(self, events: list[Event]) -> None:
        if events:
            os.write(self.fd, b"".join(pack_event(*ev) for ev in events)
                     + pack_event(EV_SYN, SYN_REPORT, 0))

    def close(self) -> None:
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        finally:
            os.close(self.fd)
