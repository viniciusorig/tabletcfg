# tabletcfg

Configura mesa digitalizadora (driver libinput) no X11/i3: monitor ou área de
tela, área da mesa, rotação, proporção e curva de pressão da caneta. Reaplica sozinho ao reconectar a mesa.

## Instalar

    ./install.sh          # cria ~/.local/bin/tabletcfg

## Usar

    tabletcfg gui         # configurar; "Salvar" ativa a reaplicação automática
    tabletcfg list | monitors | apply <perfil> | next | reset | identify
    tabletcfg install-rule | uninstall-rule
    tabletcfg pressure                      # mostra a curva do perfil e da caneta
    tabletcfg pressure firme                # muito-macia | macia | normal | firme | muito-firme
    tabletcfg pressure 40                   # -100 (macia) .. 100 (firme)
    tabletcfg pressure --curve 0.2 0 1 0.8  # curva livre; --profile NOME altera outro perfil

Atalho no i3 para alternar perfis:

    bindsym $mod+t exec --no-startup-id tabletcfg next

## Observações

- O X só cria o dispositivo da caneta quando ela chega perto da mesa pela
  primeira vez. Ao conectar a mesa (ou no login), o serviço fica esperando e
  aplica o perfil assim que a caneta se aproximar; depois sai.
- No primeiro "Salvar", a janela pede sua senha para instalar a regra udev
  (via `sudo`; a senha não é guardada). Pelo terminal: `tabletcfg install-rule`.
- Na aba "Pressão", a curva é aplicada na caneta enquanto você ajusta; fechar a
  janela sem salvar devolve a curva anterior.

## Arquivos

- `~/.config/tabletcfg/profiles.toml` — perfis
- `/etc/udev/rules.d/99-tabletcfg.rules` — regra udev (criada no primeiro Salvar)
- `~/.config/systemd/user/tabletcfg-apply.service` — aplica o perfil salvo

## Testes

    python3 -m unittest discover -s tests -t . -v
