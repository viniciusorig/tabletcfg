"""Linha de comando: tabletcfg <subcomando>."""
import argparse
import sys
import time

from . import apply as ap
from . import profiles
from .monitors import read_layout
from .proc import TabletError


def _warn(msgs):
    for m in msgs:
        print(f"aviso: {m}", file=sys.stderr)


def _apply_named(store, name):
    if name not in store.profiles:
        raise TabletError(f"Perfil '{name}' não existe (veja 'tabletcfg list')")
    res = ap.apply_profile(store.profiles[name])
    ap.write_last(name)
    _warn(res.warnings)
    print(f"Perfil '{name}' aplicado")


def cmd_apply(args):
    store = profiles.load()
    if not args.saved:
        if not args.name:
            raise TabletError("Informe o perfil ou use --saved")
        _apply_named(store, args.name)
        return 0
    # Modo do serviço automático: nunca falha ruidosamente.
    if store.saved is None:
        print("tabletcfg: nenhum perfil salvo; nada a fazer", file=sys.stderr)
        return 0
    if args.wait:
        if not ap.wait_for_session(args.wait):
            print("tabletcfg: sessão X não encontrada; nada aplicado", file=sys.stderr)
            return 0
        time.sleep(1.0)  # deixa o X registrar todos os nós da mesa recém-conectada
        if ap.wait_for_tablet(args.wait) is None:
            print("tabletcfg: mesa não encontrada; nada aplicado", file=sys.stderr)
            return 0
    try:
        _apply_named(store, store.saved)
    except ap.NoTablet as e:
        print(f"tabletcfg: {e}", file=sys.stderr)
    return 0


def cmd_list(args):
    store = profiles.load()
    if not store.profiles:
        print("Nenhum perfil. Crie um com 'tabletcfg gui'.")
    for name in sorted(store.profiles):
        mark = "*" if name == store.saved else " "
        print(f"{mark} {name}")
    return 0


def cmd_monitors(args):
    layout = read_layout()
    print(f"Desktop: {layout.width}x{layout.height}")
    for i, m in enumerate(layout.monitors, 1):
        prim = " (principal)" if m.primary else ""
        print(f"{i}: {m.name}{prim}  {m.w}x{m.h}+{m.x}+{m.y}  id={m.id}")
    return 0


def cmd_next(args):
    store = profiles.load()
    name = ap.next_name(sorted(store.profiles), ap.read_last())
    if name is None:
        raise TabletError("Nenhum perfil")
    _apply_named(store, name)
    return 0


def cmd_reset(args):
    ap.reset()
    print("Matriz restaurada (mesa em todos os monitores, sem rotação)")
    return 0


def cmd_identify(args):
    from .identify import show_identify
    show_identify(read_layout().monitors, standalone=True)
    return 0


def cmd_gui(args):
    from .gui import run_gui
    return run_gui()


def build_parser():
    p = argparse.ArgumentParser(prog="tabletcfg", description="Configura a mesa digitalizadora")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gui", help="abre a janela de configuração").set_defaults(func=cmd_gui)
    sub.add_parser("list", help="lista perfis (* = salvo)").set_defaults(func=cmd_list)
    sub.add_parser("monitors", help="lista monitores detectados").set_defaults(func=cmd_monitors)
    a = sub.add_parser("apply", help="aplica um perfil")
    a.add_argument("name", nargs="?")
    a.add_argument("--saved", action="store_true", help="aplica o perfil salvo")
    a.add_argument("--wait", type=float, default=0, metavar="SEG",
                   help="espera a sessão X e a mesa por até SEG segundos")
    a.set_defaults(func=cmd_apply)
    sub.add_parser("next", help="aplica o próximo perfil").set_defaults(func=cmd_next)
    sub.add_parser("reset", help="remove rotação e limites").set_defaults(func=cmd_reset)
    sub.add_parser("identify", help="mostra o número de cada monitor").set_defaults(func=cmd_identify)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except TabletError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
