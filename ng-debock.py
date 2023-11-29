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

import sys
import os
import argparse
import urllib.request

package_path = os.path.abspath(os.path.dirname(__file__))

ubuntu_releases = {
    'noble'  : '24.04',
    'mantic' : '23.10',
    'lunar'  : '23.04',
    'jammy'  : '22.04',
    'focal'  : '20.04',
    'bionic' : '18.04',
    'xenial' : '16.04',
    'trusty' : '14.04',
    }

ubuntu_archive_releases = {
    'kinetic'  : '22.10',
    'impish'   : '21.10',
    'hirsute'  : '21.04',
    'groovy'   : '20.10',
    'eoan'     : '19.10',
    'disco'    : '19.04',
    'cosmic'   : '18.10',
    'artful'   : '17.10',
    'zesty'    : '17.04',
    'yakkety'  : '16.10',
    'wily'     : '15.10',
    'vivid'    : '15.04',
    'utopic'   : '14.10',
    'saucy'    : '13.10',
    'raring'   : '13.04',
    'quantal'  : '12.10',
    'precise'  : '12.04',
    'oneiric'  : '11.10',
    'natty'    : '11.04',
    'maverick' : '10.10',
    'lucid'    : '10.04',
    'karmic'   :  '9.10',
    'jaunty'   :  '9.04',
    'intrepid' :  '8.10',
    'hardy'    :  '8.04',
    }

debian_releases = {
    'bookworm' : '12.0',
    'bullseye' : '11.0',
    'buster'   : '10.0',
    }

debian_archive_releases = {
    'stretch' : '9.0',
    'jessie'  : '8.0',
    'wheezy'  : '7.0',
    'squeeze' : '6.0',
    'lenny'   : '5.0',
    'etch'    : '4.0',
    'sarge'   : '3.1',
    'woody'   : '3.0',
    'potato'  : '2.2',
    }

components = {
    'ubuntu' : ['main','restricted','universe','multiverse'],
    'debian' : ['main','contrib','non-free'],
}

class Debocker:
    def __init__(self):
        self.args = None
        self.packages = set()

        self.argparser = argparse.ArgumentParser(
            description='Build docker images of old Ubuntu and Debian releases')

        self.argparser.add_argument('--arch', '-a',
            metavar='<arch>',
            help='processor architecture to build')

        self.argparser.add_argument('--packages', '-p',
            metavar='<file>',
            help='file containing list of packages to include')

        self.argparser.add_argument('--list', '-l',
            action='store_true',
            help='only ouput list of packages')

        self.argparser.add_argument('--mirror', '-m',
            metavar='<mirror>', default='',
            help='specify alternate mirror to use')

        self.argparser.add_argument('--no-letsencrypt', '-e',
            action='store_false', dest='letsencrypt',
            help='disable Let\'s Encrypt update')

        self.argparser.add_argument('--quiet', '-q',
            action='store_true',
            help='less verbose output')

        self.argparser.add_argument('release',
            nargs='?', default='',
            help='which release to build (use ? to list)')

        #self._releases = list(ubuntu_releases.keys() + ubuntu_archive_releases.keys())
        #print(self._releases)
        #ubuntu_releases
        #ubuntu_archive_releases
        #debian_releases
        #debian_archive_releases

    @classmethod
    def main(cls):
        self = cls()
        self.parse()

    def parse(self):
        self.args = self.argparser.parse_args()

        self.distro  = None
        self.archive = False

        if self.args.release in ubuntu_releases:
            self.distro = 'ubuntu'

        elif self.args.release in ubuntu_archive_releases:
            self.distro  = 'ubuntu'
            self.archive = True

        elif self.args.release in debian_releases:
            self.distro = 'debian'

        elif self.args.release in debian_archive_releases:
            self.distro  = 'debian'
            self.archive = True

        if not self.distro:
            if self.args.release:
                print(f'[!] Unknown release: {self.args.release}')
                print()
            self.list_releases()
            return

        self.load_packages()

        if self.args.list:
            self.list_packages()
            return

        self.build()

    def list_releases(self):
        def _print(header, releases):
            print(f'{header:^18}')
            print('=' * 18)
            for name,version in releases.items():
                print(f' {name:8} - {version:>5}')
            print()

        _print('Ubuntu',         ubuntu_releases)
        _print('Debian',         debian_releases)
        _print('Ubuntu Archive', ubuntu_archive_releases)
        _print('Debian Archive', debian_archive_releases)

    def load_packages(self):
        exclude = set()
        def _load(path):
            try:
                packages = open(path, 'r').readlines()
            except FileNotFoundError:
                return
            packages = [p.strip() for p in packages]
            packages = [p for p in packages if p]
            self.packages.update(p for p in packages if p[0] not in ['#',';','-'])
            exclude.update(p for p in packages if p[0] == '-')

        _load(os.path.join(package_path, 'packages'))
        _load('packages')
        _load(f'packages.{self.distro}')
        _load(f'packages.{self.args.release}')

        self.packages = list(self.packages - exclude)
        self.packages.sort()

        if self.args.letsencrypt and 'ca-certificates' not in self. packages:
            print('[!] use --no-letsencrypt when excluding ca-certificates package')
            sys.exit(-1)

    def list_packages(self):
        print('[+] Packages:')
        for package in self.packages:
            print(f'--- {package}')

    def build(self):
        if 0 != os.getuid():
            print('[!] debootstrap requires root')
            return -1


        name = f'debocker-{self.args.release}'
        tag  = f'debocker:{self.args.release}'
        if self.args.arch:
            # TODO: qemu-debootstrap is deprecated
            debootstrap = 'qemu-debootstrap'
            alt_arch = f'--arch={self.args.arch}'
            name += f'-{self.args.arch}'
            tag  += f'-{self.args.arch}'
        else:
            debootstrap = 'debootstrap'
            alt_arch = ''

        # if running in-tree use the envs subdirectory
        if package_path == os.getcwd:
            dest = os.path.join(package_path, 'envs', name)
        else:
            dest = name

        keyring = f'--keyring=/usr/share/keyrings/{self.distro}-archive-removed-keys.gpg' if self.archive else ''

        if not os.path.exists(dest):
            cmd = ' '.join([
                debootstrap,
                alt_arch,
                f'--components={",".join(components[self.distro])}',
                f'--include={",".join(self.packages)}',
                keyring,
                self.args.release,
                dest,
                self.args.mirror
                ])

            print('[+]', cmd)
            if not self.args.quiet:
                self.list_packages()
            else:
                cmd += ' > /dev/null'

            status = os.system(cmd)
            if status != 0:
                print(f'[!] Failed to debootstrap: {status}')
                return

        if self.args.letsencrypt:
            print('[+] lets encrypt')
            req  = urllib.request.Request('https://letsencrypt.org/certs/isrgrootx1.pem')
            try:
                resp = urllib.request.urlopen(req)
            except Exception as e:
                print(f'[!] {e}')
                return

            if resp.getcode() != 200:
                print(f'[!] Response code: {resp.getcode()}')
                return

            cert = resp.read(resp.length)
            cert_path = os.path.join(dest, 'usr', 'share', 'ca-certificates', 'isrgrootx1.crt')

            with open(cert_path, 'wb') as fp:
                fp.write(cert)

        print(f'[+] creating docker: {name}')
        print(os.getcwd())
        os.system(f"cd {dest} && tar -c --exclude './var/cache/apt/archives/*.deb' . | docker import - {tag}")
        print(os.getcwd())


if '__main__' == __name__:
    Debocker.main()
