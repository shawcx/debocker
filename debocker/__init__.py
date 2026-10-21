#!/usr/bin/env python3
#
# The MIT License (MIT)
# 
# Copyright (c) 2018-2023 Matthew Shaw
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

__version__ = '0.6'

import sys
import os
import re
import shlex
import shutil
import argparse
import subprocess
import urllib.request
import importlib.resources

# which /usr/share/keyrings/<distro>-archive-<keys>.gpg verifies the release
KEYRING  = 'keyring'
REMOVED  = 'removed-keys'
UNSIGNED = None # signed by a key no keyring ships, skip the check

releases = {
    # name        distro     version  keys      eol
    # Ubuntu
    'hardy'    : ('Ubuntu',  '8.04', REMOVED,  True),
    'intrepid' : ('Ubuntu',  '8.10', REMOVED,  True),
    'jaunty'   : ('Ubuntu',  '9.04', REMOVED,  True),
    'karmic'   : ('Ubuntu',  '9.10', REMOVED,  True),
    'lucid'    : ('Ubuntu', '10.04', REMOVED,  True),
    'maverick' : ('Ubuntu', '10.10', REMOVED,  True),
    'natty'    : ('Ubuntu', '11.04', REMOVED,  True),
    'oneiric'  : ('Ubuntu', '11.10', REMOVED,  True),
    'precise'  : ('Ubuntu', '12.04', REMOVED,  True),
    'quantal'  : ('Ubuntu', '12.10', KEYRING,  True),
    'raring'   : ('Ubuntu', '13.04', KEYRING,  True),
    'saucy'    : ('Ubuntu', '13.10', KEYRING,  True),
    'trusty'   : ('Ubuntu', '14.04', KEYRING, False),
    'utopic'   : ('Ubuntu', '14.10', KEYRING,  True),
    'vivid'    : ('Ubuntu', '15.04', KEYRING,  True),
    'wily'     : ('Ubuntu', '15.10', KEYRING,  True),
    'xenial'   : ('Ubuntu', '16.04', KEYRING, False),
    'yakkety'  : ('Ubuntu', '16.10', KEYRING,  True),
    'zesty'    : ('Ubuntu', '17.04', KEYRING,  True),
    'artful'   : ('Ubuntu', '17.10', KEYRING,  True),
    'bionic'   : ('Ubuntu', '18.04', KEYRING, False),
    'cosmic'   : ('Ubuntu', '18.10', KEYRING,  True),
    'disco'    : ('Ubuntu', '19.04', KEYRING,  True),
    'eoan'     : ('Ubuntu', '19.10', KEYRING,  True),
    'focal'    : ('Ubuntu', '20.04', KEYRING, False),
    'groovy'   : ('Ubuntu', '20.10', KEYRING,  True),
    'hirsute'  : ('Ubuntu', '21.04', KEYRING,  True),
    'impish'   : ('Ubuntu', '21.10', KEYRING,  True),
    'jammy'    : ('Ubuntu', '22.04', KEYRING, False),
    'kinetic'  : ('Ubuntu', '22.10', KEYRING,  True),
    'lunar'    : ('Ubuntu', '23.04', KEYRING,  True),
    'mantic'   : ('Ubuntu', '23.10', KEYRING,  True),
    'noble'    : ('Ubuntu', '24.04', KEYRING, False),
    'oracular' : ('Ubuntu', '24.10', KEYRING,  True),
    'plucky'   : ('Ubuntu', '25.04', KEYRING, False),
    'questing' : ('Ubuntu', '25.10', KEYRING, False),
    'resolute' : ('Ubuntu', '26.04', KEYRING, False),
    # Debian
    'potato'   : ('Debian',   '2.2', UNSIGNED, True),
    'woody'    : ('Debian',   '3.0', REMOVED,  True),
    'sarge'    : ('Debian',   '3.1', REMOVED,  True),
    'etch'     : ('Debian',   '4.0', REMOVED,  True),
    'lenny'    : ('Debian',   '5.0', REMOVED,  True),
    'squeeze'  : ('Debian',   '6.0', REMOVED,  True),
    'wheezy'   : ('Debian',   '7.0', REMOVED,  True),
    'jessie'   : ('Debian',   '8.0', REMOVED,  True),
    'stretch'  : ('Debian',   '9.0', KEYRING,  True),
    'buster'   : ('Debian',  '10.0', KEYRING,  True),
    'bullseye' : ('Debian',  '11.0', KEYRING, False),
    'bookworm' : ('Debian',  '12.0', KEYRING, False),
    'trixie'   : ('Debian',  '13.0', KEYRING, False),
    }

# end-of-life releases move off the regular mirrors; others use debootstrap's
# default, which picks the right mirror for the architecture
eol_mirrors = {
    'ubuntu' : 'http://old-releases.ubuntu.com/ubuntu',
    'debian' : 'http://archive.debian.org/debian',
    }

# rootfs paths kept out of the image
image_excludes = [
    './var/cache/apt/archives/*.deb',
    './var/lib/apt/lists/*_*',
    './etc/resolv.conf',
    './etc/hostname',
    ]

keyring_packages = {
    'ubuntu' : 'ubuntu-keyring',
    'debian' : 'debian-archive-keyring',
    }

# Debian security updates live in a separate archive
security_mirrors = {
    # eol    mirror
    False : 'http://security.debian.org/debian-security',
    True  : 'http://archive.debian.org/debian-security',
    }

# dpkg architecture -> qemu binfmt handler, and what each host runs natively
qemu_names = {
    'amd64'    : 'x86_64',
    'i386'     : 'i386',
    'arm64'    : 'aarch64',
    'armhf'    : 'arm',
    'armel'    : 'arm',
    'ppc64el'  : 'ppc64le',
    'powerpc'  : 'ppc',
    'ppc64'    : 'ppc64',
    's390x'    : 's390x',
    'riscv64'  : 'riscv64',
    'mips'     : 'mips',
    'mipsel'   : 'mipsel',
    'mips64el' : 'mips64el',
    'loong64'  : 'loongarch64',
    'sparc'    : 'sparc',
    'sparc64'  : 'sparc64',
    'hppa'     : 'hppa',
    'alpha'    : 'alpha',
    'm68k'     : 'm68k',
    'sh4'      : 'sh4',
    }

native_archs = {
    'amd64' : ['i386'],
    'arm64' : ['armhf', 'armel'],
    }


def apply_packages(packages, lines):
    # '#' and ';' start comments, '-name' removes a package added earlier
    for line in lines:
        name = re.split('[#;]', line, 1)[0].strip()
        if not name:
            continue
        if name[0] == '-':
            name = name[1:].strip()
            if name in packages:
                packages.remove(name)
        elif name not in packages:
            packages.append(name)
    return packages


def load_packages(release, overlay, quiet):
    # base list: ./packages.default, else the copy shipped in this package
    if os.path.exists('packages.default'):
        source = os.path.abspath('packages.default')
        with open(source, 'r') as fp:
            packages = apply_packages([], fp)
    else:
        source = importlib.resources.files(__package__).joinpath('packages.default')
        packages = apply_packages([], source.read_text().splitlines())
    if not quiet:
        print(f'[+] packages: {source}')

    # release list extends the base; only an explicit --packages must exist
    if overlay:
        overlay = overlay.format(release=release)
    elif os.path.exists(f'packages.{release}'):
        overlay = f'packages.{release}'
    if overlay:
        with open(overlay, 'r') as fp:
            apply_packages(packages, fp)
        if not quiet:
            print(f'[+] packages: {os.path.abspath(overlay)}')

    return packages


def install_certs(dest):
    # add the bundled Let's Encrypt roots through ca-certificates.conf, which
    # every ca-certificates version reads, and drop the expired DST Root CA X3
    # that old OpenSSL can pick instead of ISRG Root X1
    conf_path = os.path.join(dest, 'etc', 'ca-certificates.conf')
    if not os.path.exists(conf_path):
        print('[!] ca-certificates is not installed')
        return False

    with open(conf_path, 'r') as fp:
        conf = fp.read().splitlines()
    conf = ['!' + c if c == 'mozilla/DST_Root_CA_X3.crt' else c for c in conf]

    cert_dir = os.path.join(dest, 'usr', 'share', 'ca-certificates', 'letsencrypt')
    os.makedirs(cert_dir, exist_ok=True)
    certs = importlib.resources.files(__package__).joinpath('certs')
    for cert in sorted(certs.iterdir(), key=lambda c: c.name):
        if not cert.name.endswith('.crt'):
            continue
        with open(os.path.join(cert_dir, cert.name), 'wb') as fp:
            fp.write(cert.read_bytes())
        entry = f'letsencrypt/{cert.name}'
        if entry not in conf:
            conf.append(entry)

    with open(conf_path, 'w') as fp:
        fp.write('\n'.join(conf) + '\n')

    status = chroot(dest, ['update-ca-certificates'], quiet=True)
    if status != 0:
        print(f'[!] update-ca-certificates failed: {status}')
        return False
    return True


def chroot(dest, cmd, quiet):
    # a clean environment so the host's locale and paths don't leak in
    env = {
        'PATH'             : '/usr/sbin:/usr/bin:/sbin:/bin',
        'HOME'             : '/root',
        'LC_ALL'           : 'C',
        'DEBIAN_FRONTEND'  : 'noninteractive',
        }
    return subprocess.run(['chroot', dest] + cmd, env=env,
        stdout=subprocess.DEVNULL if quiet else None).returncode


def suite_exists(mirror, suite):
    for name in ('InRelease', 'Release'):
        req = urllib.request.Request(f'{mirror}/dists/{suite}/{name}', method='HEAD')
        try:
            urllib.request.urlopen(req, timeout=30)
            return True
        except Exception:
            pass
    return False


def update_release(dest, release, distro, eol, quiet):
    # add whichever -updates and security suites exist to the sources.list
    # debootstrap wrote, then upgrade to them
    sources_path = os.path.join(dest, 'etc', 'apt', 'sources.list')
    with open(sources_path, 'r') as fp:
        sources = fp.read().splitlines()
    base = next((s.split() for s in sources if s.startswith('deb ')), None)
    if not base:
        print(f'[!] no deb line in {sources_path}')
        return False
    url,components = base[1],base[3:]

    candidates = [[(url, f'{release}-updates')]]
    if distro == 'debian':
        security = security_mirrors[eol]
        candidates.append([(security, f'{release}-security'), (security, f'{release}/updates')])
    else:
        candidates.append([(url, f'{release}-security')])

    for choices in candidates:
        for mirror,suite in choices:
            if not suite_exists(mirror, suite):
                continue
            line = ' '.join(['deb', mirror, suite] + components)
            if line not in sources:
                print(f'[+] adding {mirror} {suite}')
                sources.append(line)
            break

    with open(sources_path, 'w') as fp:
        fp.write('\n'.join(sources) + '\n')

    # keep package scripts from starting services in the chroot
    policy = os.path.join(dest, 'usr', 'sbin', 'policy-rc.d')
    created = not os.path.exists(policy)
    if created:
        with open(policy, 'w') as fp:
            fp.write('#!/bin/sh\nexit 101\n')
        os.chmod(policy, 0o755)
    proc = os.path.join(dest, 'proc')
    mounted = 0 == subprocess.run(['mount', '-t', 'proc', 'proc', proc]).returncode

    try:
        for cmd in (
            ['apt-get', 'update'],
            ['apt-get', '-y',
                '-o', 'Dpkg::Options::=--force-confdef',
                '-o', 'Dpkg::Options::=--force-confold',
                'dist-upgrade'],
            ['apt-get', 'clean'],
            ):
            status = chroot(dest, cmd, quiet)
            if status != 0:
                print(f'[!] {shlex.join(cmd)} failed: {status}')
                return False
    finally:
        if mounted:
            subprocess.run(['umount', proc])
        if created:
            os.remove(policy)
    return True


def check_arch(arch, binfmt='/proc/sys/fs/binfmt_misc'):
    # foreign architectures run under qemu's binfmt handlers, which need the
    # F flag to keep working inside the chroot
    try:
        host = subprocess.run(['dpkg', '--print-architecture'],
            capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        host = {q: a for a,q in qemu_names.items()}.get(os.uname().machine)
    if arch == host or arch in native_archs.get(host, []):
        return True
    if arch not in qemu_names:
        print(f'[!] unknown architecture: {arch}')
        return False

    handler = os.path.join(binfmt, f'qemu-{qemu_names[arch]}')
    try:
        with open(handler, 'r') as fp:
            lines = fp.read().splitlines()
    except FileNotFoundError:
        print(f'[!] no qemu handler for {arch}, install qemu-user-static')
        return False
    flags = ''.join(l.split(':', 1)[1] for l in lines if l.startswith('flags:'))
    if 'enabled' not in lines or 'F' not in flags:
        print(f'[!] {handler} must be enabled with the F flag')
        return False
    return True


def mounts_under(path, mounts='/proc/mounts'):
    path = os.path.realpath(path)
    with open(mounts, 'r') as fp:
        points = [m.split()[1].replace('\\040', ' ') for m in fp]
    return [p for p in points if p == path or p.startswith(path + '/')]


def tar_command(dest):
    # leave out downloaded packages and indexes, and the host's network
    # identity, which docker provides at run time; lists/partial stays since
    # old apt won't create it
    return ['tar', '-C', dest, '-c', '--numeric-owner'] + [
        f'--exclude={e}' for e in image_excludes] + ['.']


def build(release, mirror, arch, packages, letsencrypt, updates, quiet):
    if 0 != os.getuid():
        print('[!] debootstrap requires root')
        return 1

    if arch and not check_arch(arch):
        return 1

    distro,version,keys,eol = releases[release]
    distro = distro.lower()
    if keys is UNSIGNED:
        print(f'[-] no keyring verifies {release}, skipping the signature check')
        keyring = ['--no-check-gpg']
    else:
        keyring_path = f'/usr/share/keyrings/{distro}-archive-{keys}.gpg'
        if not os.path.exists(keyring_path):
            print(f'[!] missing {keyring_path}, install {keyring_packages[distro]}')
            return 1
        keyring = [f'--keyring={keyring_path}']

    if not mirror and eol:
        mirror = eol_mirrors[distro]

    try:
        packages = load_packages(release, packages, quiet)
    except FileNotFoundError as e:
        print(f'[-] {e.strerror}: {e.filename}')
        return 1

    if letsencrypt:
        if 'ca-certificates' not in packages:
            packages.append('ca-certificates')

    if distro == 'ubuntu':
        components = ['main','restricted','universe','multiverse']
    elif distro == 'debian':
        components = ['main','contrib','non-free']

    name = f'debocker-{release}'
    tag  = f'debocker:{release}'
    if arch:
        name += f'-{arch}'
        tag  += f'-{arch}'

    fullpath = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
    intree = os.getcwd() == fullpath
    if intree:
        dest = os.path.join(fullpath, 'envs', name)
    else:
        dest = name

    # build in <dest>.partial and rename it once complete, so a failed build
    # is redone instead of reused
    if not os.path.exists(dest):
        partial = dest + '.partial'
        if os.path.exists(partial):
            mounts = mounts_under(partial)
            if mounts:
                print(f'[!] unmount these before rebuilding: {" ".join(mounts)}')
                return 1
            print(f'[+] removing incomplete build: {partial}')
            shutil.rmtree(partial)

        cmd = ['debootstrap']
        if arch:
            cmd.append(f'--arch={arch}')
        cmd.append(f'--components={",".join(components)}')
        cmd.append('--include=' + ','.join(packages))
        cmd.extend(keyring)
        cmd.extend([release, partial])
        if mirror:
            cmd.append(mirror)

        print('[+]', shlex.join(cmd))
        if not quiet:
            print('[+] Packages:')
            for package in packages:
                print(f' -- {package}')
            print()

        status = subprocess.run(cmd,
            stdout=subprocess.DEVNULL if quiet else None).returncode
        if status != 0:
            print(f'[!] Failed to debootstrap: {status}')
            return 1

        if updates:
            print('[+] updates')
            if not update_release(partial, release, distro, eol, quiet):
                return 1

        os.rename(partial, dest)

    if letsencrypt:
        print('[+] lets encrypt')
        if not install_certs(dest):
            return 1

    print(f'[+] creating docker: {tag}')
    tar = subprocess.Popen(tar_command(dest), stdout=subprocess.PIPE)
    docker = subprocess.Popen([
        'docker', 'import', '--change', 'CMD ["/bin/bash"]', '-', tag
        ], stdin=tar.stdout)
    tar.stdout.close()
    if docker.wait() != 0 or tar.wait() != 0:
        print(f'[!] Failed to create docker image: {tag}')
        return 1
    return 0


def main():
    argparser = argparse.ArgumentParser(
        prog='debocker',
        description='Build docker images of old Ubuntu and Debian releases'
        )

    argparser.add_argument('--version', '-V',
        action='version', version=f'%(prog)s {__version__}'
        )

    argparser.add_argument('--arch', '-a',
        metavar='<arch>',
        help='processor architecture to build (needs qemu-user-static)'
        )

    argparser.add_argument('--packages', '-p',
        metavar='<file>',
        help='packages to add to (or remove from with -name) packages.default'
             ' (default: packages.{release} if present)'
        )

    argparser.add_argument('--no-letsencrypt', '-e',
        action='store_false', dest='letsencrypt',
        help='don\'t add the Let\'s Encrypt root certificates'
        )

    argparser.add_argument('--no-updates', '-U',
        action='store_false', dest='updates',
        help='don\'t add the -updates and security suites or upgrade to them'
        )

    argparser.add_argument('--quiet', '-q',
        action='store_true',
        help='less verbose output'
        )

    argparser.add_argument('release',
        help='which release to build (use ? to list)'
        )

    argparser.add_argument('mirror',
        nargs='?', default='',
        help='mirror to download from (default: debootstrap\'s, or the'
             ' archive mirror for end-of-life releases)'
        )

    args = argparser.parse_args()

    if args.release not in releases:
        if args.release != '?':
            print(f'[!] unknown release: {args.release}')
        for release,values in releases.items():
            distro,version,keys,eol = values
            print(f'{release:8} - {distro} {version}{" (EOL)" if eol else ""}')
        return 0 if args.release == '?' else 1

    return build(**vars(args))


if '__main__' == __name__:
    sys.exit(main())
