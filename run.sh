#!/bin/bash
#
# Run InkyStock. With no arguments this performs a single update (suitable for a
# cron job or a quick test); pass --daemon to run continuously (used by the
# systemd service). Any arguments are forwarded to main.py.

# Use variables from .env file
if [ -f .env ] ; then
  set -o allexport
  source .env
  set +o allexport
fi

# Prefer uv. systemd/cron run with a minimal PATH, so look in the usual spots.
UV="$(command -v uv 2>/dev/null)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
[ -z "$UV" ] && [ -x "/usr/local/bin/uv" ] && UV="/usr/local/bin/uv"

if [ -n "$UV" ] ; then
  exec "$UV" run python main.py --config config.ini "$@"
elif [ -d .venv ] ; then
  # Fallback for platforms without a uv binary (e.g. the armv6 Pi Zero W).
  . .venv/bin/activate && exec python main.py --config config.ini "$@"
else
  echo "Neither uv nor a .venv was found. Run 'make install' first." >&2
  exit 1
fi
