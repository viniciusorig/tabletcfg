# tabletcfg

Configurador de mesa digitalizadora para Linux com **X11** e driver
**libinput** (feito e testado no i3, funciona em qualquer ambiente X11). Tem
uma janela GTK e uma linha de comando. Configura:

- **Área de desenho:** a mesa pode cobrir um monitor, todos os monitores ou só
  um pedaço da tela. Também dá para recortar a área útil da mesa, girar (0°,
  90°, 180° e 270°) e manter a proporção para o traço não sair esticado.
- **Pressão da caneta:** um deslizante de "macia" a "firme" e uma curva
  avançada com 2 pontos arrastáveis. Tem uma área de teste para desenhar e ver
  a pressão ao vivo.
- **Botões da mesa e da caneta:** cada um pode virar um atalho de teclado,
  clique do mouse, rolagem ou comando, ou ser desativado. Mesas de outros
  modelos têm um assistente que aprende os botões.
- **Perfis:** guardam tudo isso. Você troca de perfil pela janela, pelo
  terminal ou por um atalho (por exemplo, um perfil para o Krita e outro para
  o GIMP).
- **Reaplicação automática:** ao conectar a mesa, uma regra udev inicia
  serviços systemd do usuário, que reaplicam o perfil salvo e remapeiam os
  botões enquanto a mesa estiver conectada. Nenhum processo fica rodando sem a
  mesa.

Testado com a SZ PING-IT T505 (`08f2:6811`, clone da 10moon 1060N), que já vem
com o mapa de botões embutido.

## Requisitos

- Sessão **X11** (Wayland não é suportado: usa `xinput` e `xrandr`)
- Driver `xf86-input-libinput`
- Python ≥ 3.11, PyGObject com GTK 3, pyudev
- `xinput`, `xrandr`, `systemd` (sessão do usuário) e `sudo`
- Para remapear os botões: acesso de leitura ao `/dev/input/event*` da mesa e
  de escrita ao `/dev/uinput`. A leitura vem do grupo `input`; os pacotes já
  instalam uma regra para o `/dev/uinput`:

      sudo usermod -aG input $USER     # depois, saia e entre de novo na sessão

| Distribuição | Dependências |
|---|---|
| Arch | `python python-gobject gtk3 python-pyudev xorg-xinput xorg-xrandr xf86-input-libinput` |
| Debian/Ubuntu | `python3-gi gir1.2-gtk-3.0 python3-pyudev xinput x11-xserver-utils xserver-xorg-input-libinput` |
| Fedora | `python3-gobject gtk3 python3-pyudev xinput xrandr xorg-x11-drv-libinput` |

## Instalação

**Pelo código-fonte (desenvolvimento):** cria um `~/.local/bin/tabletcfg` que
aponta para esta pasta:

    ./install.sh

**Com pipx (no usuário):** o PyGObject vem do sistema, por isso o
`--system-site-packages`:

    pipx install --system-site-packages .

Nesse caso, o atalho de menu e a regra do uinput não são instalados. Copie-os
à mão se quiser:

    install -Dm644 data/tabletcfg.desktop ~/.local/share/applications/tabletcfg.desktop
    sudo install -Dm644 data/70-tabletcfg-uinput.rules /etc/udev/rules.d/70-tabletcfg-uinput.rules

**Debian 13+/Ubuntu 24.04+:** baixe o `.deb` da
[release mais recente](https://github.com/viniciusorig/tabletcfg/releases) e
instale:

    sudo apt install ./tabletcfg_0.1.0-1_all.deb

**Arch Linux:** enquanto o pacote não está no AUR, use o PKGBUILD do
repositório:

    git clone https://github.com/viniciusorig/tabletcfg.git
    cd tabletcfg/packaging/aur
    makepkg -si

Detalhes de cada formato em [Empacotamento](#empacotamento).

## Uso

    tabletcfg gui            # abre a janela

Na janela:

1. **Aba "Área de desenho":** clique no monitor desejado e arraste para limitar
   a área da tela ou da mesa. Escolha a rotação e se quer manter a proporção.
2. **Aba "Pressão":** mova o deslizante ou abra o "Avançado" e desenhe na área
   de teste. A curva vale na hora; se você fechar sem salvar, a curva anterior
   volta.
3. **Aba "Botões":** escolha a ação de cada botão. "Detectar" acha a linha do
   botão que você apertar e "Aprender botões" ensina uma mesa nova.
4. **Testar** aplica área e pressão sem salvar. **Salvar** grava o perfil,
   transforma-o no perfil automático e ativa os botões. No primeiro Salvar a
   janela pede sua senha, uma única vez, para instalar a regra udev.

Linha de comando:

    tabletcfg list                          # perfis (* = o salvo/automático)
    tabletcfg monitors                      # monitores detectados
    tabletcfg apply <perfil>                # aplica um perfil
    tabletcfg next                          # aplica o próximo perfil (bom para atalho)
    tabletcfg reset                         # tira rotação, limites e curva de pressão
    tabletcfg identify                      # mostra o número de cada monitor na tela
    tabletcfg pressure                      # curva do perfil e da caneta
    tabletcfg pressure firme                # muito-macia | macia | normal | firme | muito-firme
    tabletcfg pressure 40                   # firmeza de -100 (macia) a 100 (firme)
    tabletcfg pressure --curve 0.2 0 1 0.8  # curva livre (--profile NOME para outro perfil)
    tabletcfg buttons                       # o que cada botão faz no perfil ativo
    tabletcfg install-rule                  # instala a reaplicação automática pelo terminal
    tabletcfg uninstall-rule                # remove a regra e os serviços

Atalho no i3 para alternar perfis:

    bindsym $mod+t exec --no-startup-id tabletcfg next

## Configuração em arquivo

Os perfis ficam em `~/.config/tabletcfg/profiles.toml` e podem ser editados à
mão:

```toml
saved = "krita"

[profiles."krita"]
target = "monitor"            # "monitor" ou "all"
monitor_id = "SKG-2783-000F69B5"
monitor_name = "DP-4"
screen_area = [0.0, 0.0, 1.0, 1.0]   # x, y, largura, altura em frações
tablet_area = [0.0, 0.0, 1.0, 1.0]
rotation = 90
keep_aspect = true
pressure_curve = [0.4, 0.0, 1.0, 0.6] # pontos de controle da curva (x1 y1 x2 y2)

[profiles."krita".buttons]
tablet1 = "key ctrl+z"
tablet2 = "key ctrl+shift+z"
tablet7 = "key ctrl"                  # segurar o botão = segurar Ctrl
tablet3 = "click right"
tablet4 = "scroll up"
tablet5 = "command tabletcfg next"
pen1 = "click middle"                 # pen1 = botão da caneta mais perto da ponta
pen2 = "disable"
```

Ações possíveis: `key <atalho>`, `click left|middle|right`,
`scroll up|down|left|right`, `command <linha de shell>` e `disable`. Um botão
que não aparece na tabela continua enviando o original.

## Como funciona

- **Área e rotação:** viram a `Coordinate Transformation Matrix` dos ponteiros
  da mesa (`xinput set-prop`).
- **Pressão:** é a propriedade `libinput Tablet Tool Pressurecurve`, uma
  Bézier de 0/0 a 1/1 com dois pontos de controle.
- **A caneta aparece tarde:** o X só cria o dispositivo da caneta quando ela
  chega perto da mesa pela primeira vez. Por isso a mesa é identificada pelo
  udev, e o serviço `tabletcfg-apply` espera a caneta aparecer, aplica o perfil
  e sai.
- **Botões:** em muitas mesas baratas os botões chegam como teclas, por um
  "teclado" da própria mesa. Enquanto a mesa está conectada, o serviço
  `tabletcfg-buttons`:
  - captura esse teclado com exclusividade (`EVIOCGRAB`), para o X não receber
    as teclas originais;
  - reconhece cada botão pelo conjunto de teclas que ele envia;
  - emite as ações por um teclado e mouse virtual (`/dev/uinput`);
  - acompanha a troca de perfil;
  - solta a captura quando o perfil não remapeia nenhum botão.
- **Limite dos botões:** botões que a mesa envia pelo mesmo dispositivo da
  caneta (caso das Wacom) não são remapeados.

## Arquivos

| Caminho | O que é |
|---|---|
| `~/.config/tabletcfg/profiles.toml` | perfis |
| `~/.config/tabletcfg/devices.toml` | botões aprendidos por modelo de mesa |
| `~/.local/state/tabletcfg/last` | último perfil aplicado |
| `/etc/udev/rules.d/99-tabletcfg.rules` | regra que inicia os serviços ao conectar (criada no Salvar) |
| `~/.config/systemd/user/tabletcfg-apply.service` | aplica o perfil salvo |
| `~/.config/systemd/user/tabletcfg-buttons.service` | remapeia os botões |
| `/usr/lib/udev/rules.d/70-tabletcfg-uinput.rules` | acesso ao `/dev/uinput` (pacotes) |

## Problemas comuns

- **"Aproxime a caneta da mesa":** o X ainda não criou a caneta; encoste a
  caneta perto da mesa uma vez.
- **Os botões não fazem nada:**
  - veja se você está no grupo `input` (`id`);
  - veja se o serviço está ativo (`systemctl --user status tabletcfg-buttons`);
  - leia o log com `journalctl --user -u tabletcfg-buttons -n 30`.
- **O perfil não volta ao reconectar a mesa:** leia o log com
  `journalctl --user -u tabletcfg-apply -n 20` e confira se
  `/etc/udev/rules.d/99-tabletcfg.rules` existe.

## Desenvolvimento

    python3 -m unittest discover -s tests -t . -v

Dependências: só a biblioteca padrão do Python, mais PyGObject e pyudev. O
código está em `tabletcfg/`:

| Arquivo | Conteúdo |
|---|---|
| `matrix.py` | matemática da matriz |
| `profiles.py` | perfis em TOML |
| `pressure.py` | curva de pressão |
| `keys.py` | nomes de teclas |
| `buttons.py` | ações, mapa de botões e remapeamento (sem E/S) |
| `evdev.py` | evdev e uinput |
| `remap.py` | serviço dos botões |
| `*_ui.py` e `gui.py` | interface GTK |

## Empacotamento

Os arquivos ficam em `packaging/`. Todos instalam o comando
`/usr/bin/tabletcfg`, o atalho de menu (`tabletcfg.desktop`) e a regra
`70-tabletcfg-uinput.rules`. A regra udev da mesa e os serviços systemd do
usuário são criados pelo próprio programa no primeiro Salvar, porque dependem
do modelo de mesa conectado.

**Antes de publicar uma versão:**

1. Publique o repositório. Os arquivos supõem `https://github.com/viniciusorig/tabletcfg`;
   se for outro endereço, troque o `url`/`Homepage`/`URL` nos três arquivos.
2. Atualize a versão em `pyproject.toml`, `tabletcfg/__init__.py`,
   `packaging/aur/PKGBUILD`, `packaging/debian/changelog` e
   `packaging/rpm/tabletcfg.spec`.
3. Crie e envie a tag: `git tag v0.1.0 && git push origin v0.1.0`.

### AUR (Arch Linux)

`packaging/aur/PKGBUILD` baixa o tarball da tag.

    cd packaging/aur
    updpkgsums                         # troca o SKIP pelo sha256 real (pacman-contrib)
    makepkg --printsrcinfo > .SRCINFO
    makepkg -si                        # testa: compila, roda os testes e instala
    namcap PKGBUILD *.pkg.tar.zst      # opcional: verificação de boas práticas

Para publicar, é preciso ter uma conta no AUR com chave SSH cadastrada:

    git clone ssh://aur@aur.archlinux.org/tabletcfg.git aur-tabletcfg
    cp PKGBUILD .SRCINFO aur-tabletcfg/
    cd aur-tabletcfg && git add PKGBUILD .SRCINFO && git commit -m "tabletcfg 0.1.0" && git push

O nome `tabletcfg` estava livre no AUR em 2026-10-07. Para uma versão que
acompanha o `master`, crie também um `tabletcfg-git` com
`source=("git+$url.git")` e uma função `pkgver()`.

### apt (Debian/Ubuntu)

Os arquivos de `packaging/debian/` usam debhelper com pybuild. É preciso
Python ≥ 3.11: Debian 12+ ou Ubuntu 23.04+.

    sudo apt install build-essential devscripts debhelper dh-python \
        pybuild-plugin-pyproject python3-all python3-setuptools python3-wheel
    curl -L -o ../tabletcfg_0.1.0.orig.tar.gz \
        https://github.com/viniciusorig/tabletcfg/archive/refs/tags/v0.1.0.tar.gz
    cp -r packaging/debian debian
    dpkg-buildpackage -us -uc          # gera ../tabletcfg_0.1.0-1_all.deb
    sudo apt install ../tabletcfg_0.1.0-1_all.deb
    lintian ../tabletcfg_0.1.0-1_*.changes   # opcional

Fora do Debian (por exemplo, no Arch), gere o pacote num contêiner:

    docker run --rm -v "$PWD":/src:ro -v "$PWD/dist":/out debian:trixie bash -c '
      apt-get update && apt-get install -y build-essential debhelper dh-python \
        pybuild-plugin-pyproject python3-all python3-setuptools python3-wheel curl &&
      mkdir /build && cd /build &&
      curl -L -o tabletcfg_0.1.0.orig.tar.gz \
        https://github.com/viniciusorig/tabletcfg/archive/refs/tags/v0.1.0.tar.gz &&
      tar xzf tabletcfg_0.1.0.orig.tar.gz && cd tabletcfg-0.1.0 &&
      cp -r packaging/debian debian && dpkg-buildpackage -us -uc &&
      cp ../tabletcfg_0.1.0-1_all.deb /out/ && chown '"$(id -u)"' /out/*.deb'

Caminhos de distribuição:
- **PPA no Launchpad (Ubuntu):** assine o pacote fonte com `debuild -S -sa` e
  envie com `dput ppa:<usuario>/<ppa> ../tabletcfg_0.1.0-1_source.changes`.
  Antes, troque `unstable` no `debian/changelog` pela série do Ubuntu (ex.:
  `noble`).
- **Repositório apt próprio:** use `reprepro` ou `aptly`.
- **Debian oficial:** abra um ITP (bug "Intent To Package" no pacote `wnpp`) e
  procure um sponsor em mentors.debian.net.

### dnf (Fedora/RHEL)

`packaging/rpm/tabletcfg.spec` segue as diretrizes de Python do Fedora
(`pyproject-rpm-macros`).

    sudo dnf install rpm-build rpmdevtools python3-devel systemd-rpm-macros desktop-file-utils
    rpmdev-setuptree
    spectool -g -R packaging/rpm/tabletcfg.spec   # baixa o tarball da tag para ~/rpmbuild/SOURCES
    rpmbuild -ba packaging/rpm/tabletcfg.spec
    sudo dnf install ~/rpmbuild/RPMS/noarch/tabletcfg-0.1.0-1.*.noarch.rpm

Caminhos de distribuição:
- **COPR:** é o caminho mais simples para oferecer `dnf install`. Crie um
  projeto em copr.fedorainfracloud.org e envie o SRPM
  (`~/rpmbuild/SRPMS/*.src.rpm`) ou aponte para o repositório. Os usuários
  instalam com:

      sudo dnf copr enable viniciusorig/tabletcfg
      sudo dnf install tabletcfg

- **Fedora oficial:** abra um "Review Request" no Bugzilla do Fedora e entre
  no grupo de packagers.

## Licença

GPL-3.0-or-later. Veja [LICENSE](LICENSE).
