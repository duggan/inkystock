.PHONY: deps install dev codestyle mypy test

deps:
	apt-get install -y libtiff-dev libopenjp2-7-dev libatlas-base-dev libopenblas-dev python3-pip python3-dev python3-venv
install:
	test -d .venv || python3 -m venv .venv
	. .venv/bin/activate && python -m pip install -r requirements.txt
	mkdir -p data
cron.5m:
	cp -f resources/cron-inkystock-5m /etc/cron.d/cron-inkystock
dev:
	. .venv/bin/activate && python -m pip install --no-deps -r dev-requirements.txt
codestyle:
	. .venv/bin/activate && python -m pycodestyle --max-line-length=120 ./
mypy:
	. .venv/bin/activate && python -m mypy --namespace-packages --ignore-missing-imports --follow-imports=skip --strict-optional ./

test: codestyle mypy
