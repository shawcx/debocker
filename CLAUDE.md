# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What it is

`debocker` builds Docker base images of old (often EOL) Ubuntu and Debian releases: it runs `debootstrap` into a directory, then pipes a tarball of that rootfs into `docker import`. The whole tool is `debocker/__init__.py` (run with `python3 -m debocker`); `setup.py` installs it as the `debocker` console script.

## Commands

There are no tests, linter config, or build steps beyond packaging.

```sh
python3 -m debocker ?                        # list known releases (any unknown name prints the list)
sudo python3 -m debocker xenial [mirror]
sudo python3 -m debocker -a armhf bionic     # non-native arch via qemu-debootstrap
pip install .                                # install the `debocker` entry point
```

Host prerequisites: root, `debootstrap` (plus `qemu-debootstrap`/qemu-user-static for `--arch`), Docker, and `debian-keyring debian-archive-keyring` (and Ubuntu's keyring) for the archive keys.

## How `build()` works

- **Release table**: `releases` maps codename → `(distro, version, isOld)`. Adding a release means adding a row. `isOld=True` makes debootstrap use `/usr/share/keyrings/{distro}-archive-removed-keys.gpg`, since keys for EOL releases have been moved out of the active keyring.
- **Package list** (`load_packages`): the base is `./packages.default` if present, else the copy bundled in the package (`debocker/packages.default`, read via `importlib.resources`). Then `./packages.{release}` (or the `--packages` file, `{release}`-formatted; an explicit one must exist) is applied on top. `apply_packages` handles both files: `#`/`;` start comments, `-name` removes a package added earlier, and duplicates are dropped with order kept. `.gitignore` ignores `/packages.*`, so the cwd lists are local-only.
- **Output location**: if run from the repo directory, the rootfs goes to `envs/debocker-<release>[-<arch>]` (gitignored); otherwise to `./debocker-<release>[-<arch>]` in the cwd. An existing rootfs dir is reused (debootstrap is skipped), so delete it to force a rebuild.
- **Let's Encrypt** (on unless `-e`): adds `ca-certificates` and drops ISRG Root X1 into the rootfs at `usr/share/ca-certificates/isrgrootx1.crt` so old releases can reach modern TLS sites.
- **Image tag**: `debocker:<release>[-<arch>]`. `.deb` files in the apt cache are excluded from the import.
- Shell commands are assembled as strings and run with `os.system`.

## Style

The `releases` table and `setup.py` use hand-aligned columns; keep them aligned. Status output uses `[+]` / `[-]` / `[!]` prefixes.
