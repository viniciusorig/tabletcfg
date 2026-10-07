"""Linha de comando: tabletcfg <subcomando>."""
import argparse
import sys

from . import apply as ap
from . import pressure, profiles
from .devices import tablet_present
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
    if args.follow:
        def log(msg):
            print(f"tabletcfg: {msg}", file=sys.stderr, flush=True)
        ap.follow_apply(lambda: _apply_named(store, store.saved), tablet_present, log=log)
        return 0
    try:
        _apply_named(store, store.saved)
    except (ap.NoTablet, ap.PenNotReady) as e:
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
    print("Matriz e pressão restauradas (mesa em todos os monitores, sem rotação, curva linear)")
    return 0


def cmd_identify(args):
    from .identify import show_identify
    show_identify(read_layout().monitors, standalone=True)
    return 0


def active_profile(store, explicit: str | None, last: str | None) -> str:
    """Perfil afetado por 'pressure': --profile, senão o último aplicado, senão o salvo."""
    if explicit is not None:
        if explicit not in store.profiles:
            raise TabletError(f"Perfil '{explicit}' não existe (veja 'tabletcfg list')")
        return explicit
    for name in (last, store.saved):
        if name in store.profiles:
            return name
    raise TabletError("Nenhum perfil ativo; informe --profile NOME")


def describe_curve(curve) -> str:
    s = pressure.firmness_of(curve)
    label = pressure.preset_label(curve)
    if s is not None:
        n = round(s * 100)
        label += f" ({n:+d})" if n else " (0)"
    return f"{label}  [{' '.join(f'{v:g}' for v in curve)}]"


def cmd_pressure(args):
    store = profiles.load()
    last = ap.read_last()
    name = active_profile(store, args.profile, last)
    if args.value is None and args.curve is None:
        print(f"Perfil '{name}': {describe_curve(store.profiles[name].pressure_curve)}")
        pen = ap.read_pen_curve()
        print(f"Caneta: {describe_curve(pen) if pen else 'caneta não detectada'}")
        return 0
    if args.value is not None and args.curve is not None:
        raise TabletError("Use a firmeza ou --curve, não os dois")
    if args.curve is not None:
        curve = pressure.validate_curve(args.curve)
    else:
        curve = pressure.curve_for_firmness(pressure.parse_firmness(args.value))
    store.profiles[name].pressure_curve = curve
    profiles.save(store)
    print(f"Pressão do perfil '{name}': {describe_curve(curve)}")
    if name != active_profile(store, None, last):
        print(f"(não é o perfil ativo; aplique com 'tabletcfg apply {name}')")
        return 0
    try:
        ap.apply_curve(curve)
    except (ap.NoTablet, ap.PenNotReady) as e:
        print(f"aviso: {e}\naviso: aproxime a caneta e rode 'tabletcfg apply {name}'",
              file=sys.stderr)
    return 0


def cmd_buttons(args):
    from . import remap
    from .buttons import ButtonMap, action_label
    from .keys import combo_label
    if args.follow:
        return remap.follow_buttons()
    bmap = remap.current_map()
    if bmap is None:
        raise TabletError("Botões desta mesa desconhecidos (ou mesa desconectada); "
                          "use 'Aprender botões' na janela")
    store = profiles.load()
    name, actions, warnings = remap.actions_for(bmap, store, ap.read_last())
    _warn(warnings)
    print(f"Perfil '{name}':" if name else "Nenhum perfil ativo:")
    for button in bmap.ids():
        action = actions.get(button)
        label = action_label(action) if action else "Original"
        print(f"  {ButtonMap.label(button):<10} {combo_label(bmap.signature(button)):<12} → {label}")
    return 0


def cmd_gui(args):
    from .gui import run_gui
    return run_gui()


def cmd_install_rule(args):
    from . import autorule
    from .devices import find_tablet
    _warn(autorule.ensure_auto_apply(find_tablet()))
    print(f"Serviço: {autorule.service_path()}\nRegra: {autorule.RULES_PATH}")
    return 0


def cmd_uninstall_rule(args):
    from . import autorule
    autorule.uninstall()
    print("Regra automática removida")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="tabletcfg", description="Configura a mesa digitalizadora")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gui", help="abre a janela de configuração").set_defaults(func=cmd_gui)
    sub.add_parser("list", help="lista perfis (* = salvo)").set_defaults(func=cmd_list)
    sub.add_parser("monitors", help="lista monitores detectados").set_defaults(func=cmd_monitors)
    a = sub.add_parser("apply", help="aplica um perfil")
    a.add_argument("name", nargs="?")
    a.add_argument("--saved", action="store_true", help="aplica o perfil salvo")
    a.add_argument("--follow", action="store_true",
                   help="espera a caneta aparecer no X e aplica (usado pelo serviço)")
    a.set_defaults(func=cmd_apply)
    sub.add_parser("next", help="aplica o próximo perfil").set_defaults(func=cmd_next)
    pr = sub.add_parser("pressure", help="mostra ou ajusta a curva de pressão da caneta")
    pr.add_argument("value", nargs="?", metavar="FIRMEZA",
                    help="muito-macia, macia, normal, firme, muito-firme ou -100..100")
    pr.add_argument("--curve", nargs=4, type=float, metavar=("X1", "Y1", "X2", "Y2"),
                    help="curva livre (pontos de controle em 0..1)")
    pr.add_argument("--profile", help="perfil a alterar (padrão: o ativo)")
    pr.set_defaults(func=cmd_pressure)
    b = sub.add_parser("buttons", help="mostra o que cada botão faz no perfil ativo")
    b.add_argument("--follow", action="store_true",
                   help="remapeia os botões enquanto a mesa estiver conectada (usado pelo serviço)")
    b.set_defaults(func=cmd_buttons)
    sub.add_parser("reset", help="remove rotação, limites e curva de pressão").set_defaults(func=cmd_reset)
    sub.add_parser("identify", help="mostra o número de cada monitor").set_defaults(func=cmd_identify)
    sub.add_parser("install-rule", help="instala a reaplicação automática").set_defaults(func=cmd_install_rule)
    sub.add_parser("uninstall-rule", help="remove a reaplicação automática").set_defaults(func=cmd_uninstall_rule)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except TabletError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
