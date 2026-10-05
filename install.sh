#!/bin/sh
# Instala o comando `tabletcfg` em ~/.local/bin apontando para este repositório.
set -e
repo="$(cd "$(dirname "$0")" && pwd)"
bin="$HOME/.local/bin"
mkdir -p "$bin"
cat > "$bin/tabletcfg" <<EOF
#!/bin/sh
PYTHONPATH="$repo\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m tabletcfg "\$@"
EOF
chmod +x "$bin/tabletcfg"
echo "Instalado: $bin/tabletcfg"
