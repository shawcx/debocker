# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What it is

`debocker` builds Docker base images of old (often EOL) Ubuntu and Debian releases: it runs `debootstrap` into a directory, then pipes a tarball of that rootfs into `docker import`. The whole tool is `debocker/__init__.py` (run with `python3 -m debocker`); `setup.py` installs it as the `debocker` console script.

## Commands

There's no linter config.

```sh
python3 -m debocker ?                        # list known releases (any unknown name prints the list)
sudo python3 -m debocker xenial [mirror]
sudo python3 -m debocker -a armhf bionic     # foreign arch via qemu-user-static
pip install .                                # install the `debocker` entry point
make test                                    # pytest, offline; single test: python3 -m pytest -k mounts_under
make check-releases                          # verify the release table against the live archives
make wheel                                   # dist/debocker-<ver>-py3-none-any.whl
make man                                     # dist/debocker.1 via help2man
make deb                                     # dist/debocker_<ver>_all.deb (needs pybuild-plugin-pyproject, help2man)
```

Tests (`tests/test_debocker.py`) stub out everything needing root or the network: `chroot`, `suite_exists`, and `subprocess.run` for `mount`, plus the `binfmt`/`mounts` path parameters of `check_arch`/`mounts_under`. They do run the real `tar_command` against a temporary tree. `tools/check_releases.py` is the network check: run it after editing `releases`, and now and then as releases go end-of-life. It needs `debian-archive-keyring` and `ubuntu-keyring` installed, or `-k <dir>` pointing at both. The deb build runs the tests through pybuild and generates the man page from `--help` (`execute_after_dh_auto_build`), so help text changes flow into `debocker.1`.

Packaging: `pyproject.toml` (setuptools) defines the `debocker` script and bundles `debocker/packages.default` and `debocker/certs/*.crt`. `debian/` is a native (`3.0 (native)`) dh + pybuild package that installs `/usr/bin/debocker`. To release, bump the version in both `debocker/__init__.py` (`__version__`, which pyproject reads) and `debian/changelog`.

Host prerequisites: root, `debootstrap`, Docker, `debian-archive-keyring` and `ubuntu-keyring`. `--arch` builds also need qemu-user-static, whose binfmt handlers let debootstrap's second stage and the `chroot` calls run foreign binaries.

## How `build()` works

- **Release table**: `releases` maps codename → `(distro, version, keys, eol)`. Adding a release means adding a row, and both flags should be checked against the live archives rather than guessed.
  - `keys` names the keyring passed to debootstrap: `KEYRING` is `/usr/share/keyrings/<distro>-archive-keyring.gpg`, `REMOVED` is `...-archive-removed-keys.gpg`, and `UNSIGNED` (potato, signed by a key no keyring ships) means `--no-check-gpg`. debootstrap accepts a Release file if *any* signature verifies, so a release signed by both an old and a current key (quantal–xenial, stretch) works with `KEYRING`. To check, run `gpgv --status-fd 1 --keyring <kr> Release.gpg Release` and look for `VALIDSIG`.
  - `eol=True` switches the default mirror to `eol_mirrors` (old-releases.ubuntu.com / archive.debian.org; both carry all architectures). Supported releases get no mirror argument, so debootstrap picks one itself (archive vs ports by architecture). A release is EOL here once its `dists/<release>/Release` is gone from archive.ubuntu.com / deb.debian.org.
- **Package list** (`load_packages`): the base is `./packages.default` if present, else the copy bundled in the package (`debocker/packages.default`, read via `importlib.resources`). Then `./packages.{release}` (or the `--packages` file, `{release}`-formatted; an explicit one must exist) is applied on top. `apply_packages` handles both files: `#`/`;` start comments, `-name` removes a package added earlier, and duplicates are dropped with order kept. `.gitignore` ignores `/packages.*`, so the cwd lists are local-only.
- **Output location**: if run from the repo directory, the rootfs goes to `envs/debocker-<release>[-<arch>]` (gitignored); otherwise to `./debocker-<release>[-<arch>]` in the cwd. A fresh build happens in `<dest>.partial` and is renamed only after debootstrap and the update step succeed. A leftover `.partial` is deleted on the next run, but only if nothing is mounted under it (`mounts_under`), because `rmtree` through a still-mounted `/proc` or `/dev` would reach the host. An existing finished rootfs is reused (debootstrap and updates are skipped), so delete it to force a rebuild.
- **Updates** (`update_release`, on unless `-U`; fresh builds only): appends to debootstrap's `etc/apt/sources.list` whichever of `<release>-updates` and the security suite exist, checked with a HEAD request. For Ubuntu the security suite is `<release>-security` on the same mirror; for Debian it's on `security_mirrors` as `<release>-security` (bullseye+) or `<release>/updates`. Then it runs `apt-get update`, `dist-upgrade` (keeping existing config files), and `clean` in the chroot, with `/proc` mounted and a temporary `policy-rc.d` that stops services from starting. All chroot calls go through `chroot()` with a clean environment.
- **Foreign architectures** (`check_arch`): anything the host can't run natively (`native_archs`) needs an enabled `/proc/sys/fs/binfmt_misc/qemu-<name>` handler with the `F` flag, so it still works inside the chroot. `qemu_names` maps dpkg architectures to handler names.
- **Let's Encrypt** (`install_certs`, on unless `-e`): adds `ca-certificates`, copies the bundled ISRG roots (X1, X2 and Generation Y's YR, YE) to `usr/share/ca-certificates/letsencrypt/`, lists them in `etc/ca-certificates.conf` (the only mechanism every ca-certificates version honours; `/usr/local/share/ca-certificates` is newer), disables the expired `mozilla/DST_Root_CA_X3.crt` with `!`, then runs `chroot <dest> update-ca-certificates`. It's idempotent on a reused rootfs. Releases with OpenSSL 0.9.8/early 1.0.1 still can't negotiate with many modern servers; the roots only fix trust.
- **Image**: `tar_command` (`--numeric-owner`, leaving out `image_excludes`: apt's cached .debs and downloaded lists, plus the host's `etc/resolv.conf`/`etc/hostname`, which docker supplies at run time; `lists/partial` stays because old apt won't recreate it) piped into `docker import --change 'CMD ["/bin/bash"]'`, tagged `debocker:<release>[-<arch>]`.
- Commands run through `subprocess` with argument lists. `build()`/`main()` return an exit status, which `__main__.py` and the console script pass to `sys.exit`.

## Style

The `releases` table and other dict literals use hand-aligned columns; keep them aligned. Status output uses `[+]` / `[-]` / `[!]` prefixes.
