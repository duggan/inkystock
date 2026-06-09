.PHONY: deps install service cron.5m dev codestyle mypy test

deps:
	apt-get install -y libtiff-dev libopenjp2-7-dev python3-pip python3-dev python3-venv

install:
	@if command -v uv >/dev/null 2>&1 ; then \
		echo "Installing with uv (including Pi hardware deps)..." ; \
		uv sync --extra pi ; \
	else \
		echo "uv not found; falling back to pip + venv..." ; \
		test -d .venv || python3 -m venv .venv ; \
		. .venv/bin/activate && python -m pip install -r requirements.txt ; \
	fi
	mkdir -p data

# Run InkyStock continuously as a systemd service (recommended): imports and the
# hardware probe are paid once, not on every update.
service:
	cp -f resources/inkystock.service /etc/systemd/system/inkystock.service
	sed -i s/username/${SUDO_USER}/g /etc/systemd/system/inkystock.service
	systemctl daemon-reload
	systemctl enable --now inkystock.service
	@echo "InkyStock daemon installed and started. Follow logs: journalctl -u inkystock -f"

# Alternative to the daemon: update every 5 minutes via cron (one process per run).
cron.5m:
	cp -f resources/cron-inkystock-5m /etc/cron.d/cron-inkystock && sed -i s/username/${SUDO_USER}/g /etc/cron.d/cron-inkystock

dev:
	@if command -v uv >/dev/null 2>&1 ; then \
		uv sync --extra pi --group dev ; \
	else \
		. .venv/bin/activate && python -m pip install --no-deps -r dev-requirements.txt ; \
	fi

codestyle:
	. .venv/bin/activate && python -m pycodestyle --max-line-length=120 ./

mypy:
	. .venv/bin/activate && python -m mypy --namespace-packages --ignore-missing-imports --follow-imports=skip --strict-optional ./

test: codestyle mypy
