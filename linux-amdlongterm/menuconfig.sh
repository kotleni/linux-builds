#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
_SRCNAME="$(bash -c 'source ./PKGBUILD >/dev/null 2>&1; printf "%s" "$_srcname"')"
SRCDIR="$SCRIPT_DIR/src/$_SRCNAME"
if [[ ! -f "$SRCDIR/Kconfig" ]]; then
  makepkg -o --nobuild
fi
cp config "$SRCDIR/.config"
make -C "$SRCDIR" menuconfig
make -C "$SRCDIR" olddefconfig
if ! cmp -s "$SRCDIR/.config" config; then
  cp "$SRCDIR/.config" config
fi
