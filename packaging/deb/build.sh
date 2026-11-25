#!/bin/bash
# Monta o pacote codyn_<versão>_all.deb a partir do estado atual do repo.
#
# Uso:
#   packaging/deb/build.sh [versão]
#
# Sem argumento, usa BIN/versao.py (fonte única — é o mesmo valor mostrado na
# interface e em Help > About). Antes de rodar: 1) atualize BIN/versao.py,
# 2) adicione a entrada correspondente no topo de packaging/deb/changelog.
# Regras de numeração em packaging/VERSIONING.md.
#
# O .deb resultante é gravado em packaging/dist/.

set -euo pipefail
umask 022

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST_DIR="$PROJECT_ROOT/packaging/dist"
VERSAO_CODIGO="$(sed -n 's/^VERSAO = "\(.*\)"$/\1/p' "$PROJECT_ROOT/BIN/versao.py")"
VERSAO_CHANGELOG="$(sed -n '1s/^codyn (\(.*\)).*/\1/p' "$SCRIPT_DIR/changelog")"
if [ -z "$VERSAO_CODIGO" ] || [ "$VERSAO_CODIGO" != "$VERSAO_CHANGELOG" ]; then
    echo "build.sh: BIN/versao.py ($VERSAO_CODIGO) e o topo de packaging/deb/changelog" >&2
    echo "          ($VERSAO_CHANGELOG) estão em versões diferentes — atualize os dois" >&2
    echo "          antes de empacotar (ver packaging/VERSIONING.md)." >&2
    exit 1
fi
VERSION="${1:-$VERSAO_CODIGO}"

for tool in dpkg-deb rsync gzip; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "build.sh: dependência ausente: $tool" >&2
        exit 1
    fi
done

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> Preparando staging em $STAGE"
mkdir -p \
    "$STAGE/DEBIAN" \
    "$STAGE/opt/codyn" \
    "$STAGE/usr/bin" \
    "$STAGE/usr/share/applications" \
    "$STAGE/usr/share/doc/codyn" \
    "$STAGE/usr/share/lintian/overrides"

echo "==> Copiando arquivos da aplicação para /opt/codyn"
# PROJECTS/, RUNS/, DADOS/, LIGANDS/, TARGET/ e .form_data.json são dados do usuário e
# nunca entram no pacote.
rsync -a \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.git/' \
    --exclude='/TUTORIALS/source/' \
    "$PROJECT_ROOT/CODYN.py" \
    "$PROJECT_ROOT/BIN" \
    "$PROJECT_ROOT/ICONS" \
    "$PROJECT_ROOT/BASE" \
    "$PROJECT_ROOT/TEST" \
    "$PROJECT_ROOT/TUTORIALS" \
    "$PROJECT_ROOT/LICENSE.txt" \
    "$PROJECT_ROOT/README.md" \
    "$STAGE/opt/codyn/"

find "$STAGE/opt/codyn" -type d -exec chmod 755 {} +
find "$STAGE/opt/codyn" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/opt/codyn/CODYN.py"

echo "==> Instalando launcher e menu"
install -m 755 "$SCRIPT_DIR/codyn-launcher" "$STAGE/usr/bin/codyn"
install -m 644 "$SCRIPT_DIR/codyn.desktop" "$STAGE/usr/share/applications/codyn.desktop"
install -m 644 "$SCRIPT_DIR/copyright" "$STAGE/usr/share/doc/codyn/copyright"
install -m 644 "$SCRIPT_DIR/lintian-overrides" "$STAGE/usr/share/lintian/overrides/codyn"
install -m 644 "$PROJECT_ROOT/README.md" "$STAGE/usr/share/doc/codyn/README.md"
gzip -9nc "$SCRIPT_DIR/changelog" > "$STAGE/usr/share/doc/codyn/changelog.Debian.gz"
chmod 644 "$STAGE/usr/share/doc/codyn/changelog.Debian.gz"

echo "==> Gerando DEBIAN/control (versão $VERSION)"
INSTALLED_SIZE="$(du -sk "$STAGE/opt/codyn" | cut -f1)"
sed \
    -e "s/@VERSION@/$VERSION/" \
    -e "s/@INSTALLED_SIZE@/$INSTALLED_SIZE/" \
    "$SCRIPT_DIR/control.in" > "$STAGE/DEBIAN/control"

install -m 755 "$SCRIPT_DIR/postinst" "$STAGE/DEBIAN/postinst"
install -m 755 "$SCRIPT_DIR/postrm" "$STAGE/DEBIAN/postrm"

mkdir -p "$DIST_DIR"
OUT_DEB="$DIST_DIR/codyn_${VERSION}_all.deb"

echo "==> Empacotando $OUT_DEB"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT_DEB"

if command -v lintian >/dev/null 2>&1; then
    echo "==> lintian (informativo, não interrompe o build)"
    lintian "$OUT_DEB" || true
fi

echo "==> Pronto: $OUT_DEB"
