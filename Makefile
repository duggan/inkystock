.PHONY: deploy install dev codestyle mypy test

deploy:
	rsync --delete --progress -av --exclude data --exclude .env . pi@pizero1:inkystock/
install:
	python3 -m pip install -r requirements.txt
	mkdir -p data
cron.5m:
	cp -f resources/cron-inkystock-5m /etc/cron.d/cron-inkystock
dev:
	python3 -m pip install --no-deps -r dev-requirements.txt
codestyle:
	python3 -m pycodestyle --max-line-length=120 ./
mypy:
	python3 -m mypy --namespace-packages --ignore-missing-imports --follow-imports=skip --strict-optional ./

test: codestyle mypy
