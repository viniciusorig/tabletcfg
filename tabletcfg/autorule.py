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
HEADER = "# Gerado por tabletcfg — não editar à mão\n"
NO_AGENT_HELP = ("Nenhum agente polkit rodando para pedir a senha. Rode 'tabletcfg install-rule' "
                 "num terminal, ou instale polkit-gnome e adicione ao i3: exec --no-startup-id "
                 "/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1")
IDS_RE = re.compile(r'ATTRS\{idVendor\}=="(\w+)".*ATTRS\{idProduct\}=="(\w+)"')


def service_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "systemd" / "user" / SERVICE_NAME


def rule_line(vendor: str, product: str) -> str:
    return (f'ACTION=="add", SUBSYSTEM=="input", KERNEL=="event*", ENV{{ID_INPUT_TABLET}}=="1", '
            f'ATTRS{{idVendor}}=="{vendor}", ATTRS{{idProduct}}=="{product}", '
            f'TAG+="systemd", ENV{{SYSTEMD_USER_WANTS}}+="{SERVICE_NAME}"')


def parse_rule_ids(text: str) -> set[tuple[str, str]]:
    return {(m.group(1), m.group(2)) for m in IDS_RE.finditer(text)}


def render_rules(ids: set[tuple[str, str]]) -> str:
    return HEADER + "".join(rule_line(v, p) + "\n" for v, p in sorted(ids))


def render_service(exe: str) -> str:
    return (
        "[Unit]\n"
        "Description=Aplicar perfil salvo da mesa digitalizadora\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={exe} apply --saved --follow\n"
    )


def rule_needs_update(current: str | None, vendor: str, product: str) -> bool:
    return current is None or (vendor, product) not in parse_rule_ids(current)


def executable() -> str:
    return shutil.which("tabletcfg") or str(Path.home() / ".local" / "bin" / "tabletcfg")


def install_service(exe: str | None = None) -> None:
    path = service_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_service(exe or executable()), encoding="utf-8")
    run(["systemctl", "--user", "daemon-reload"])


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def install_rule(vendor: str, product: str, rules_path: Path = RULES_PATH) -> None:
    ids = parse_rule_ids(_read(rules_path) or "") | {(vendor, product)}
    fd, tmp = tempfile.mkstemp(prefix="tabletcfg-", suffix=".rules")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(render_rules(ids))
        os.chmod(tmp, 0o644)
        run(["pkexec", "sh", "-c",
             'install -m644 "$1" "$2" && udevadm control --reload-rules',
             "sh", tmp, str(rules_path)])
    except CommandError as e:
        if "authentication agent" in str(e):
            raise CommandError(NO_AGENT_HELP) from None
        raise
    finally:
        Path(tmp).unlink(missing_ok=True)


def uninstall(rules_path: Path = RULES_PATH) -> None:
    if rules_path.exists():
        run(["pkexec", "sh", "-c", 'rm -f "$1" && udevadm control --reload-rules',
             "sh", str(rules_path)])
    service_path().unlink(missing_ok=True)
    run(["systemctl", "--user", "daemon-reload"], check=False)


def ensure_auto_apply(tablet: Tablet | None, rules_path: Path = RULES_PATH) -> list[str]:
    warnings = []
    try:
        install_service()
    except TabletError as e:
        warnings.append(f"Serviço systemd não instalado: {e}")
    if tablet is None or not (tablet.vendor and tablet.product):
        warnings.append("Mesa não conectada: regra automática não criada "
                        "(salve de novo com a mesa conectada)")
        return warnings
    if rule_needs_update(_read(rules_path), tablet.vendor, tablet.product):
        try:
            install_rule(tablet.vendor, tablet.product, rules_path)
        except CommandError as e:
            warnings.append(f"Regra automática não instalada: {e}")
    return warnings
