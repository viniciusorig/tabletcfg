"""Execução de comandos externos com erros legíveis."""
import subprocess

PACKAGES = {
    "xrandr": "xorg-xrandr",
    "xinput": "xorg-xinput",
    "pkexec": "polkit",
    "systemctl": "systemd",
}


class TabletError(Exception):
    pass


class ToolMissing(TabletError):
    pass


class CommandError(TabletError):
    pass


def run(args: list[str], check: bool = True) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True)
    except FileNotFoundError:
        pkg = PACKAGES.get(args[0], args[0])
        raise ToolMissing(f"Comando '{args[0]}' não encontrado; instale o pacote {pkg}") from None
    if check and r.returncode != 0:
        raise CommandError(f"'{' '.join(args)}' falhou ({r.returncode}): {r.stderr.strip()}")
    return r.stdout
