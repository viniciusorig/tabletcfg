# tabletcfg

Configura mesa digitalizadora (driver libinput) no X11/i3: monitor ou área de
tela, área da mesa, rotação e proporção. Reaplica sozinho ao reconectar a mesa.

## Instalar

    ./install.sh          # cria ~/.local/bin/tabletcfg

## Usar

    tabletcfg gui         # configurar; "Salvar" ativa a reaplicação automática
    tabletcfg list | monitors | apply <perfil> | next | reset | identify
    tabletcfg install-rule | uninstall-rule

Atalho no i3 para alternar perfis:

    bindsym $mod+t exec --no-startup-id tabletcfg next

## Observações

- O X só cria o dispositivo da caneta quando ela chega perto da mesa pela
  primeira vez. Ao conectar a mesa (ou no login), o serviço fica esperando e
  aplica o perfil assim que a caneta se aproximar; depois sai.
- No primeiro "Salvar", a janela pede sua senha para instalar a regra udev
  (via `sudo`; a senha não é guardada). Pelo terminal: `tabletcfg install-rule`.

## Arquivos

- `~/.config/tabletcfg/profiles.toml` — perfis
- `/etc/udev/rules.d/99-tabletcfg.rules` — regra udev (criada no primeiro Salvar)
- `~/.config/systemd/user/tabletcfg-apply.service` — aplica o perfil salvo

## Testes

    python3 -m unittest discover -s tests -t . -v
