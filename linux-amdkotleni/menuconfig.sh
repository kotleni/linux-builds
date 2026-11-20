#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
PKGVER="$(bash -c 'source ./PKGBUILD >/dev/null 2>&1; printf "%s" "$pkgver"')"
SRCDIR="$SCRIPT_DIR/src/linux-$PKGVER"
if [[ ! -f "$SRCDIR/Kconfig" ]]; then
  makepkg -o --nobuild
fi
cp config.amd-desktop-x86_64 "$SRCDIR/.config"
make -C "$SRCDIR" menuconfig
make -C "$SRCDIR" olddefconfig
if ! cmp -s "$SRCDIR/.config" config; then
  cp "$SRCDIR/.config" config.amd-desktop-x86_64
fi
