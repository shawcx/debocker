#!/usr/bin/env python3

import sys
import os
import argparse
import collections
import urllib.request

    # name        distro     version  old
releases = collections.OrderedDict([
	# Ubuntu
    ('hardy'    , ('Ubuntu',  '8.04', True)),
    ('intrepid' , ('Ubuntu',  '8.10', True)),
    ('jaunty'   , ('Ubuntu',  '9.04', True)),
    ('karmic'   , ('Ubuntu',  '9.10', True)),
    ('lucid'    , ('Ubuntu', '10.04', True)),
    ('maverick' , ('Ubuntu', '10.10', True)),
    ('natty'    , ('Ubuntu', '11.04', True)),
    ('oneiric'  , ('Ubuntu', '11.10', True)),
    ('precise'  , ('Ubuntu', '12.04', True)),
    ('quantal'  , ('Ubuntu', '12.10', True)),
    ('raring'   , ('Ubuntu', '13.04', True)),
    ('saucy'    , ('Ubuntu', '13.10', True)),
    ('trusty'   , ('Ubuntu', '14.04', False)),
    ('utopic'   , ('Ubuntu', '14.10', True)),
    ('vivid'    , ('Ubuntu', '15.04', True)),
    ('wily'     , ('Ubuntu', '15.10', True)),
    ('xenial'   , ('Ubuntu', '16.04', False)),
    ('yakkety'  , ('Ubuntu', '16.10', True)),
    ('zesty'    , ('Ubuntu', '17.04', True)),
    # As of Oct 2019 debootstrap needs updates to support artful
    ('artful'   , ('Ubuntu', '17.10', True)),
    ('bionic'   , ('Ubuntu', '18.04', False)),
    ('cosmic'   , ('Ubuntu', '18.10', True)),
    ('disco'    , ('Ubuntu', '19.04', False)),
    ('eoan'     , ('Ubuntu', '19.10', False)),
    # Debian
    ('potato'   , ('Debian',   '2.2', True)),
    ('woody'    , ('Debian',   '3.0', True)),
    ('sarge'    , ('Debian',   '3.1', True)),
    ('etch'     , ('Debian',   '4.0', True)),
    ('lenny'    , ('Debian',   '5.0', True)),
    ('squeeze'  , ('Debian',   '6.0', True)),
    ('wheezy'   , ('Debian',   '7.0', True)),
    ('jessie'   , ('Debian',   '8.0', False)),
    ('stretch'  , ('Debian',   '9.0', False)),
    ('buster'   , ('Debian',  '10.0', False)),
    ('bullseye' , ('Debian',  '11.0', False)),
    ('bookworm' , ('Debian',  '12.0', False)),
    ])


def build(release, arch, packages, clean, letsencrypt):
    if 0 != os.getuid():
        print('[!] debootstrap requires root')
        return

    distro,version,isOld = releases[release]
    if isOld:
        distro = distro.lower()
        keyring = '--keyring=/usr/share/keyrings/'+distro+'-archive-removed-keys.gpg'
    else:
        keyring = ''

    packages = open(packages, 'r').readlines()
    packages = [p.strip() for p in packages]

    dest = release + '-' + arch

    if clean:
    	print('[+] removing', dest)
    	os.system('rm -rf ' + dest)

    cmd = ' '.join([
        'debootstrap',
        keyring,
        '--arch=' + arch,
        '--include=' + ','.join(p for p in packages if p and p[0] != '#'),
        release,
        dest
        ])

    print('[+] debootstrap:', cmd)
    status = os.system(cmd)
    if status != 0:
        print('[!] Failed to debootstrap:', status)
        return

    if letsencrypt:
        print('[+] lets encrypt')
        req  = urllib.request.Request('https://letsencrypt.org/certs/isrgrootx1.pem')
        try:
            resp = urllib.request.urlopen(req)
        except Exception as e:
            print('[!]', e)
            return

        if resp.getcode() != 200:
            print('[!] Response code:', resp.getcode())
            return

        cert = resp.read(resp.length)
        cert_path = os.path.join(dest, 'usr', 'share', 'ca-certificates', 'isrgrootx1.crt')

        with open(cert_path, 'wb') as fp:
            fp.write(cert)

    print('[+] cleanup')
    archives = os.path.join(dest, 'var', 'cache', 'apt', 'archives')
    os.system('rm -rf ' + archives + '/*.deb')

    print('[+] creating docker:', dest)
    if clean:
        os.system('docker image rm ' + dest)
    os.system('cd ' + dest + '&& tar -c . | docker import - ' + dest)


def main():
    argparser = argparse.ArgumentParser(
        description='Build docker images of old Ubuntu and Debian releases',
        epilog='hello'
        )

    argparser.add_argument('--arch', '-a',
        metavar='<arch>', default='i386',
        help='processor architecture to build'
        )

    argparser.add_argument('--packages', '-p',
        metavar='<file>', default='packages.default',
        help='list of packages to include'
        )

    argparser.add_argument('--no-letsencrypt', '-e',
        action='store_false', dest='letsencrypt',
        help='disable Let\'s Encrypt update'
        )

    argparser.add_argument('--clean', '-c',
        action='store_true',
        help='clear cache and docker'
        )

    argparser.add_argument('release',
        help='which release to build (use ? to list)'
        )

    args = argparser.parse_args()

    if args.release not in releases:
        for release,values in releases.items():
            distro,version,isOld = values
            print('%-8s - %s %s' % (release, distro, version))
        return

    build(**dict(args._get_kwargs()))


if '__main__' == __name__:
    main()
