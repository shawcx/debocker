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

# Configuring

The base package list is `packages.default` in the current directory, or the one shipped with debocker if there isn't one.

`packages.<release>` in the current directory (e.g. `packages.focal`) extends the base list. Specify a different file with `--packages`; `{release}` in the name is replaced with the release.

One package per line. Empty lines are ignored, and `#` or `;` start a comment. A line like `-vim` removes a package listed earlier, so `-vim` in `packages.focal` drops `vim` from `packages.default`.

Defaults to the system architecture, specify an alternate architecture with --arch.
