"""Reaplicação automática: regra udev → serviço systemd do usuário."""
import os
import re
import shutil
import tempfile
from pathlib import Path

from .devices import Tablet
from .proc import CommandError, TabletError, run

RULES_PATH = Path("/etc/udev/rules.d/99-tabletcfg.rules")
SERVICE_NAME = "tabletcfg-apply.service"
BUTTONS_SERVICE = "tabletcfg-buttons.service"
HEADER = "# Gerado por tabletcfg — não editar à mão\n"
SUDO_BAD_PASSWORD = ("incorrect password", "Sorry, try again", "no password was provided")
MAX_PASSWORD_TRIES = 3
IDS_RE = re.compile(r'ATTRS\{idVendor\}=="(\w+)".*ATTRS\{idProduct\}=="(\w+)"')


class WrongPassword(CommandError):
    pass


def service_path(name: str = SERVICE_NAME) -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "systemd" / "user" / name


def rule_line(vendor: str, product: str) -> str:
    return (f'ACTION=="add", SUBSYSTEM=="input", KERNEL=="event*", ENV{{ID_INPUT_TABLET}}=="1", '
            f'ATTRS{{idVendor}}=="{vendor}", ATTRS{{idProduct}}=="{product}", '
            f'TAG+="systemd", ENV{{SYSTEMD_USER_WANTS}}+="{SERVICE_NAME}"')


def buttons_rule_line(vendor: str, product: str) -> str:
    return (f'ACTION=="add", SUBSYSTEM=="input", KERNEL=="event*", ENV{{ID_INPUT_KEY}}=="1", '
            f'ATTRS{{idVendor}}=="{vendor}", ATTRS{{idProduct}}=="{product}", '
            f'TAG+="systemd", ENV{{SYSTEMD_USER_WANTS}}+="{BUTTONS_SERVICE}"')


def parse_rule_ids(text: str) -> set[tuple[str, str]]:
    return {(m.group(1), m.group(2)) for m in IDS_RE.finditer(text)}


def render_rules(ids: set[tuple[str, str]]) -> str:
    return HEADER + "".join(rule_line(v, p) + "\n" + buttons_rule_line(v, p) + "\n"
                            for v, p in sorted(ids))


def render_service(exe: str) -> str:
    return (
        "[Unit]\n"
        "Description=Aplicar perfil salvo da mesa digitalizadora\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={exe} apply --saved --follow\n"
    )


def render_buttons_service(exe: str) -> str:
    return (
        "[Unit]\n"
        "Description=Remapear os botões da mesa digitalizadora\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={exe} buttons --follow\n"
    )


def rule_needs_update(current: str | None, vendor: str, product: str) -> bool:
    """Também atualiza regras de versões antigas (texto gerado diferente)."""
    if current is None:
        return True
    return current != render_rules(parse_rule_ids(current) | {(vendor, product)})


def executable() -> str:
    return shutil.which("tabletcfg") or str(Path.home() / ".local" / "bin" / "tabletcfg")


def install_service(exe: str | None = None) -> None:
    exe = exe or executable()
    for name, text in ((SERVICE_NAME, render_service(exe)),
                       (BUTTONS_SERVICE, render_buttons_service(exe))):
        path = service_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    run(["systemctl", "--user", "daemon-reload"])


def start_buttons_service() -> None:
    """Com a mesa já conectada a regra udev não dispara; inicia agora (idempotente)."""
    run(["systemctl", "--user", "start", BUTTONS_SERVICE])


def stop_buttons_service() -> None:
    run(["systemctl", "--user", "stop", BUTTONS_SERVICE], check=False)


def buttons_service_active() -> bool:
    return run(["systemctl", "--user", "is-active", BUTTONS_SERVICE], check=False).strip() == "active"


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def run_as_root(script: str, args: list[str], password: str | None = None) -> None:
    """Sem senha: sudo pergunta no terminal. Com senha (GUI): vai pelo stdin, nunca nos argumentos."""
    if password is None:
        run(["sudo", "sh", "-c", script, "sh", *args])
        return
    try:
        run(["sudo", "-S", "-k", "-p", "", "sh", "-c", script, "sh", *args],
            input=password + "\n", env={"LC_ALL": "C"})
    except CommandError as e:
        if any(s in str(e) for s in SUDO_BAD_PASSWORD):
            raise WrongPassword("Senha incorreta") from None
        raise


def install_rule(vendor: str, product: str, rules_path: Path = RULES_PATH,
                 password: str | None = None) -> None:
    ids = parse_rule_ids(_read(rules_path) or "") | {(vendor, product)}
    fd, tmp = tempfile.mkstemp(prefix="tabletcfg-", suffix=".rules")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(render_rules(ids))
        os.chmod(tmp, 0o644)
        run_as_root('install -m644 "$1" "$2" && udevadm control --reload-rules',
                    [tmp, str(rules_path)], password)
    finally:
        Path(tmp).unlink(missing_ok=True)


def uninstall(rules_path: Path = RULES_PATH) -> None:
    if rules_path.exists():
        run_as_root('rm -f "$1" && udevadm control --reload-rules', [str(rules_path)])
    stop_buttons_service()
    service_path().unlink(missing_ok=True)
    service_path(BUTTONS_SERVICE).unlink(missing_ok=True)
    run(["systemctl", "--user", "daemon-reload"], check=False)


def ensure_auto_apply(tablet: Tablet | None, ask_password=None,
                      rules_path: Path = RULES_PATH) -> list[str]:
    """ask_password(retry: bool) -> str | None (None = cancelado); sem ele, sudo usa o terminal."""
    warnings = []
    try:
        install_service()
    except TabletError as e:
        warnings.append(f"Serviço systemd não instalado: {e}")
    if tablet is None or not (tablet.vendor and tablet.product):
        warnings.append("Mesa não conectada: regra automática não criada "
                        "(salve de novo com a mesa conectada)")
        return warnings
    try:
        start_buttons_service()
    except TabletError as e:
        warnings.append(f"Serviço dos botões não iniciado: {e}")
    if not rule_needs_update(_read(rules_path), tablet.vendor, tablet.product):
        return warnings
    for attempt in range(MAX_PASSWORD_TRIES):
        password = None
        if ask_password is not None:
            password = ask_password(attempt > 0)
            if password is None:
                warnings.append("Regra automática não instalada (senha cancelada)")
                break
        try:
            install_rule(tablet.vendor, tablet.product, rules_path, password)
            break
        except WrongPassword:
            if ask_password is None or attempt == MAX_PASSWORD_TRIES - 1:
                warnings.append("Regra automática não instalada: senha incorreta")
                break
        except CommandError as e:
            warnings.append(f"Regra automática não instalada: {e}")
            break
    return warnings
