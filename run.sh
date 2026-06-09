#!/bin/bash
#
# Run InkyStock. With no arguments this performs a single update (suitable for a
# cron job or a quick test); pass --daemon to run continuously (used by the
# systemd service). Any arguments are forwarded to main.py.

# Always run from the project directory so relative paths (config.ini, .venv,
# resources/) resolve regardless of where we're invoked from.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

# Use variables from .env file
if [ -f .env ] ; then
  set -o allexport
  source .env
  set +o allexport
fi

# Prefer running the project's virtualenv interpreter directly. Doing so makes
# the Python process the service's main PID, which keeps systemd's Type=notify
# watchdog working — `uv run` would fork Python as a child and its readiness
# notification would be rejected.
if [ -x .venv/bin/python ] ; then
  exec .venv/bin/python main.py --config config.ini "$@"
fi

# No virtualenv yet: fall back to uv (it will create/sync one). systemd/cron run
# with a minimal PATH, so look in the usual install spots too.
UV="$(command -v uv 2>/dev/null)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
[ -z "$UV" ] && [ -x "/usr/local/bin/uv" ] && UV="/usr/local/bin/uv"
if [ -n "$UV" ] ; then
  exec "$UV" run python main.py --config config.ini "$@"
fi

echo "Neither a .venv nor uv was found. Run 'make install' first." >&2
exit 1
