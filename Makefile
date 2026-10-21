VERSION := $(shell dpkg-parsechangelog -S Version)

.PHONY: test check-releases wheel deb man clean

test:
	python3 -m pytest

check-releases:
	tools/check_releases.py

wheel:
	python3 -m pip wheel --no-deps --wheel-dir dist .

deb:
	dpkg-buildpackage -us -uc -b
	mkdir -p dist
	mv ../debocker_$(VERSION)_* dist/

man:
	mkdir -p dist
	PYTHONPATH=. help2man --no-info --name='build Docker images of old Ubuntu and Debian releases' --output=dist/debocker.1 'python3 -m debocker'

clean:
	rm -rf build dist *.egg-info .pytest_cache
	dh_clean
