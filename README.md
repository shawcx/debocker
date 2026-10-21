debocker
========

Build docker images of old Ubuntu and Debian releases

# Installing

Build and install the Debian package (needs `pybuild-plugin-pyproject`):

    make deb
    sudo apt install ./dist/debocker_*_all.deb

The package pulls in debootstrap, the archive keyrings and Docker. Install `qemu-user-static` to build other architectures.

Or install with pip (`pip install .`), and install the dependencies yourself:

    sudo apt install debootstrap debian-archive-keyring ubuntu-keyring docker.io

# Usage

    sudo debocker <release> [mirror]
    debocker ?            # list releases
    docker run -it debocker:<release>

End-of-life releases are fetched from old-releases.ubuntu.com or archive.debian.org unless you give a mirror.

The image's apt sources get the release's `-updates` and security suites where they exist, and the image is upgraded to them, so it has each package's final version. Disable this with `--no-updates`.

Archived Debian releases are signed with keys that have since expired, so apt in those images can't authenticate packages. When debocker detects this, it adds `/etc/apt/apt.conf.d/99debocker-unauthenticated` to the image so apt still installs packages. Delete that file to restore the checks.

A failed build is left in `debocker-<release>.partial` for inspection and redone on the next run. A finished `debocker-<release>` directory is reused, so delete it to rebuild from scratch.

By default the Let's Encrypt root certificates (ISRG Root X1, X2, YR and YE) are added to the image's CA store, and the expired DST Root CA X3 is disabled, so old releases can verify current certificates. Disable this with `--no-letsencrypt`. Releases with very old OpenSSL may still be unable to connect to servers that require newer TLS.

# Configuring

The base package list is `packages.default` in the current directory, or the one shipped with debocker if there isn't one.

`packages.<release>` in the current directory (e.g. `packages.focal`) extends the base list. Specify a different file with `--packages`; `{release}` in the name is replaced with the release.

One package per line. Empty lines are ignored, and `#` or `;` start a comment.

`a | b` installs the first of `a` and `b` that the release has, so a package renamed between releases can be listed once, e.g. `libelf1t64 | libelf1 | libelfg0`. Packages are checked against the release's index before anything is downloaded, and a package with no match stops the build.

A line like `-vim` removes every entry naming `vim`, so `-vim` in `packages.focal` drops `vim` from `packages.default`.

Defaults to the system architecture, specify an alternate architecture with --arch.

# Development

    make test             # unit tests (pytest)
    make check-releases   # check the release table against the live archives
    tools/check_releases.py --packages   # also check packages.default resolves everywhere
