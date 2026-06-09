#!/usr/bin/env bash
#
# InkyStock installer for a fresh Raspberry Pi OS (64-bit).
#
# Standard install (from main):
#
#   curl -fsSL https://raw.githubusercontent.com/duggan/inkystock/main/install.sh | sudo bash
#
# Install a specific branch or tag (handy for testing a PR):
#
#   curl -fsSL https://raw.githubusercontent.com/duggan/inkystock/<ref>/install.sh \
#       | sudo bash -s -- --ref <ref>
#
# This enables SPI/I2C, installs system + Python dependencies (via uv), drops the
# app into ~/inkystock for the invoking user, and starts the systemd service. The
# default configuration needs no API keys (Coinbase, BTC in EUR).
#
set -euo pipefail

REPO="duggan/inkystock"
REF="${INKYSTOCK_REF:-main}"

while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF="${2:?--ref needs a value}"; shift 2 ;;
    --ref=*) REF="${1#*=}"; shift ;;
    -h|--help)
      echo "Usage: install.sh [--ref <branch-or-tag>]   (default ref: main)"
      exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

log() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "This installer needs root (apt, raspi-config, systemd). Run via: curl ... | sudo bash" >&2
  exit 1
fi

# The app should be owned and run by an unprivileged user, not root.
TARGET_USER="${SUDO_USER:-${INKYSTOCK_USER:-}}"
if [ -z "$TARGET_USER" ] || [ "$TARGET_USER" = "root" ]; then
  TARGET_USER="$(getent passwd 1000 | cut -d: -f1 || true)"
  [ -z "$TARGET_USER" ] && TARGET_USER="pi"
fi
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
if [ -z "$TARGET_HOME" ]; then
  echo "Could not determine the home directory for user '$TARGET_USER'." >&2
  exit 1
fi
TARGET_DIR="$TARGET_HOME/inkystock"

log "Installing InkyStock (ref: $REF) for user '$TARGET_USER' into $TARGET_DIR"

log "Installing system packages"
apt-get update -y
apt-get install -y curl unzip libtiff-dev libopenjp2-7-dev python3 python3-venv python3-pip

if command -v raspi-config >/dev/null 2>&1; then
  log "Enabling SPI and I2C"
  raspi-config nonint do_spi 0 || true
  raspi-config nonint do_i2c 0 || true
else
  log "raspi-config not found; skipping SPI/I2C enable (not a Raspberry Pi?)"
fi

log "Downloading $REPO@$REF"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL "https://github.com/$REPO/archive/$REF.zip" -o "$TMP/src.zip"
unzip -qq "$TMP/src.zip" -d "$TMP"
# GitHub names the extracted dir inkystock-<ref-with-slashes-as-dashes>; glob it.
SRC="$(find "$TMP" -maxdepth 1 -type d -name 'inkystock-*' | head -n1)"
if [ -z "$SRC" ]; then
  echo "Could not find the extracted source directory." >&2
  exit 1
fi

log "Installing into $TARGET_DIR"
mkdir -p "$TARGET_DIR"

# Existing install? Stop the old updater(s) first so two of them don't fight over
# the SPI bus and panel.
if command -v systemctl >/dev/null 2>&1; then
  systemctl stop inkystock.service >/dev/null 2>&1 || true
fi
if [ -f /etc/cron.d/cron-inkystock ]; then
  log "Removing the old 5-minute cron job (the service replaces it)"
  rm -f /etc/cron.d/cron-inkystock
fi

# Carry the user's config forward — the fresh tree ships a default config.ini that
# would otherwise overwrite it. (.env, data/ and any .git checkout are left in
# place by the merge copy below.)
for keep in config.ini .env; do
  if [ -f "$TARGET_DIR/$keep" ]; then
    cp -a "$TARGET_DIR/$keep" "$SRC/$keep"
    log "  keeping your existing $keep"
  fi
done
if grep -qsE '^[[:space:]]*provider[[:space:]]*=[[:space:]]*IEX' "$SRC/config.ini"; then
  log "  NOTE: your config uses the IEX provider, which has been removed (IEX Cloud shut down)."
  log "        Edit config.ini to 'provider = Yahoo' (stocks) or 'provider = Coinbase' (crypto)."
fi

# Rebuild the virtualenv from scratch so dependencies are clean (e.g. switching an
# old pip .venv to uv). Price history in data/ is left untouched.
rm -rf "$TARGET_DIR/.venv"

# Copy the new code over the install. Same-named files are updated; existing
# data/ (price history), .env and a .git checkout are preserved.
cp -a "$SRC/." "$TARGET_DIR/"
chown -R "$TARGET_USER":"$TARGET_USER" "$TARGET_DIR"

log "Installing uv (if needed) and Python dependencies"
sudo -u "$TARGET_USER" env HOME="$TARGET_HOME" PATH="$TARGET_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin" \
  bash -c '
    set -euo pipefail
    # uv has no armv6 binary; if its installer fails, make install falls back to pip.
    command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh || true
    cd "$HOME/inkystock"
    make install
  '

if command -v systemctl >/dev/null 2>&1; then
  log "Installing and starting the systemd service"
  ( cd "$TARGET_DIR" && SUDO_USER="$TARGET_USER" make service )
else
  log "systemd not found; skipping service. Start manually with ./run.sh or cron."
fi

echo
log "Done. InkyStock is installed at $TARGET_DIR"
echo "    The default config uses Coinbase (BTC in EUR) with no API key."
echo "    Edit $TARGET_DIR/config.ini to change the currency, asset, or provider."
if command -v systemctl >/dev/null 2>&1; then
  echo "    Status: systemctl status inkystock"
  echo "    Logs:   journalctl -u inkystock -f"
fi
