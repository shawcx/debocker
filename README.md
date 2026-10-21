debocker
========

Build docker images of old Ubuntu and Debian releases

# Dependencies

## Ubuntu

`apt install debian-keyring debian-archive-keyring`

# Configuring

The base package list is `packages.default` in the current directory, or the one shipped with debocker if there isn't one.

`packages.<release>` in the current directory (e.g. `packages.focal`) extends the base list. Specify a different file with `--packages`; `{release}` in the name is replaced with the release.

One package per line. Empty lines are ignored, and `#` or `;` start a comment. A line like `-vim` removes a package listed earlier, so `-vim` in `packages.focal` drops `vim` from `packages.default`.

Defaults to the system architecture, specify an alternate architecture with --arch.
