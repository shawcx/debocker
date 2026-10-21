#!/usr/bin/env python3
#
# Check debocker's release table against the live archives: each release must
# be on the mirror it will be fetched from (eol), and its Release file must
# verify with the keyring it names (keys), the way debootstrap checks it. With
# --packages, also check that the bundled packages.default resolves.
#

import os
import sys
import argparse
import tempfile
import subprocess
import urllib.request
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import debocker

main_mirrors = {
    'ubuntu' : 'http://archive.ubuntu.com/ubuntu',
    'debian' : 'http://deb.debian.org/debian',
    }


def fetch(url):
    try:
        return urllib.request.urlopen(url, timeout=30).read()
    except Exception:
        return None


def verifies(keyring, sig, release):
    # debootstrap accepts the Release file if any signature is valid
    if not os.path.exists(keyring):
        return None
    out = subprocess.run(['gpgv', '--status-fd', '1', '--keyring', keyring, sig, release],
        capture_output=True, text=True).stdout
    return 'VALIDSIG' in out


def check(release, values, keyring_dir, tmp):
    distro,version,keys,eol = values
    distro = distro.lower()
    problems = []

    on_main = fetch(f'{main_mirrors[distro]}/dists/{release}/Release')
    on_eol = fetch(f'{debocker.eol_mirrors[distro]}/dists/{release}/Release')
    if eol and on_main:
        problems.append('marked eol but still on the main mirror')
    if not eol and not on_main:
        problems.append('not on the main mirror' + (', should be eol' if on_eol else ''))

    data = on_eol if eol else on_main
    sig = fetch(f'{debocker.eol_mirrors[distro] if eol else main_mirrors[distro]}/dists/{release}/Release.gpg')
    if not data or not sig:
        return release, problems or ['no Release or Release.gpg to verify']

    release_path = os.path.join(tmp, release)
    with open(release_path, 'wb') as fp:
        fp.write(data)
    with open(release_path + '.gpg', 'wb') as fp:
        fp.write(sig)

    results = {}
    for name in (debocker.KEYRING, debocker.REMOVED):
        keyring = os.path.join(keyring_dir, f'{distro}-archive-{name}.gpg')
        results[name] = verifies(keyring, release_path + '.gpg', release_path)
        if results[name] is None:
            return release, problems + [f'missing {keyring}']

    working = [name for name,ok in results.items() if ok]
    if not results[keys]:
        problems.append(f'{keys} does not verify' + (f', use {working[0]}' if working else ''))

    return release, problems


def check_packages(release, values):
    # amd64 where the release has it, else i386 for the oldest releases
    distro,version,keys,eol = values
    distro = distro.lower()
    components = debocker.distro_components[distro]
    packages = debocker.apply_packages([],
        debocker.importlib.resources.files('debocker').joinpath('packages.default').read_text().splitlines())
    for arch in ('amd64', 'i386'):
        try:
            index = debocker.PackageIndex(debocker.release_mirror(distro, eol, arch), release, arch, components)
        except FileNotFoundError:
            continue
        resolved,missing = debocker.resolve_packages(packages, index)
        return release, [f'{arch} has none of: {", ".join(missing)}'] if missing else []
    return release, ['no amd64 or i386 package index']


def main():
    argparser = argparse.ArgumentParser(description='Check the release table against the live archives')
    argparser.add_argument('--keyring-dir', '-k', metavar='<dir>', default='/usr/share/keyrings',
        help='directory holding the <distro>-archive-*.gpg keyrings')
    argparser.add_argument('--packages', '-p', action='store_true',
        help='also check that packages.default resolves (downloads package indexes)')
    args = argparser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        with concurrent.futures.ThreadPoolExecutor(16) as pool:
            jobs = [pool.submit(check, r, v, args.keyring_dir, tmp) for r,v in debocker.releases.items()]
            results = [j.result() for j in jobs]
            if args.packages:
                jobs = [pool.submit(check_packages, r, v) for r,v in debocker.releases.items()]
                for (release,problems),job in zip(results, jobs):
                    problems.extend(job.result()[1])

    failed = 0
    for release,problems in results:
        for problem in problems:
            print(f'[!] {release}: {problem}')
        failed += bool(problems)
    print(f'[+] {len(results) - failed} of {len(results)} releases ok')
    return 1 if failed else 0


if '__main__' == __name__:
    sys.exit(main())
