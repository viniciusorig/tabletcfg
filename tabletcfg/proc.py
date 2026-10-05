"""Execução de comandos externos com erros legíveis."""
import os
import subprocess

PACKAGES = {
    "xrandr": "xorg-xrandr",
    "xinput": "xorg-xinput",
    "sudo": "sudo",
    "systemctl": "systemd",
}


class TabletError(Exception):
    pass


class ToolMissing(TabletError):
    pass


class CommandError(TabletError):
    pass


def run(args: list[str], check: bool = True, input: str | None = None,
        env: dict[str, str] | None = None) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, input=input,
                           env={**os.environ, **env} if env else None)
    except FileNotFoundError:
        pkg = PACKAGES.get(args[0], args[0])
        raise ToolMissing(f"Comando '{args[0]}' não encontrado; instale o pacote {pkg}") from None
    if check and r.returncode != 0:
        raise CommandError(f"'{' '.join(args)}' falhou ({r.returncode}): {r.stderr.strip()}")
    return r.stdout
