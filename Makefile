.PHONY: update install test

update:
	git pull
	python -m pip install -e '.[dev]'
	python -c "from ace_lite.version import get_version_info; print(get_version_info())"

install:
	python -m venv .venv
	. .venv/bin/activate && python -m pip install -e '.[dev]'

test:
	python -m pytest -q

