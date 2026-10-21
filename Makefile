VERSION := $(shell dpkg-parsechangelog -S Version)

.PHONY: wheel deb clean

wheel:
	python3 -m pip wheel --no-deps --wheel-dir dist .

deb:
	dpkg-buildpackage -us -uc -b
	mkdir -p dist
	mv ../debocker_$(VERSION)_* dist/

clean:
	rm -rf build dist *.egg-info
	dh_clean
