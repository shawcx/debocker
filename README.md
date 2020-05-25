debocker
========

Build docker images of old Ubuntu and Debian releases

# Dependencies

## Ubuntu

`apt install debian-keyring debian-archive-keyring`

# Configuring

Add packages to packages.default or specify an alternat file with --package. Empty lines and lines starting with '#' are ignored.

The default architecture is i386, specify an alternate architecture with --arch.
