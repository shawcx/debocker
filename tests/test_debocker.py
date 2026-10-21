import os
import tarfile
import subprocess
import importlib.resources

import pytest

import debocker


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def bundled(name):
    return importlib.resources.files('debocker').joinpath(name)


# package lists

def test_apply_packages_comments_and_blanks():
    lines = ['a', '', '   ', '# comment', '; comment', 'b # trailing', 'c;trailing', '  d  ']
    assert debocker.apply_packages([], lines) == ['a', 'b', 'c', 'd']


def test_apply_packages_removal_and_duplicates():
    packages = debocker.apply_packages([], ['a', 'b', 'c', 'b'])
    assert packages == ['a', 'b', 'c']
    assert debocker.apply_packages(packages, ['-b', '- c', '-missing', 'd', 'a']) == ['a', 'd']


def test_apply_packages_readd_after_removal():
    assert debocker.apply_packages(['a', 'b'], ['-a', 'a']) == ['b', 'a']


def test_load_packages_bundled_default(workdir):
    expected = debocker.apply_packages([], bundled('packages.default').read_text().splitlines())
    assert expected
    assert debocker.load_packages('focal', None, True) == expected


def test_load_packages_local_default_replaces_bundled(workdir):
    (workdir / 'packages.default').write_text('one\ntwo\n')
    assert debocker.load_packages('focal', None, True) == ['one', 'two']


def test_load_packages_release_overlay(workdir):
    (workdir / 'packages.default').write_text('vim\nwget\n')
    (workdir / 'packages.focal').write_text('-vim\ncurl # extra\n')
    assert debocker.load_packages('focal', None, True) == ['wget', 'curl']
    assert debocker.load_packages('jammy', None, True) == ['vim', 'wget']


def test_load_packages_overlay_extends_bundled(workdir):
    base = debocker.apply_packages([], bundled('packages.default').read_text().splitlines())
    (workdir / 'packages.focal').write_text(f'-{base[0]}\nextra\n')
    assert debocker.load_packages('focal', None, True) == base[1:] + ['extra']


def test_load_packages_explicit_overlay(workdir):
    (workdir / 'packages.default').write_text('vim\n')
    (workdir / 'mine.focal').write_text('htop\n')
    (workdir / 'packages.focal').write_text('ignored\n')
    assert debocker.load_packages('focal', 'mine.{release}', True) == ['vim', 'htop']


def test_load_packages_explicit_overlay_must_exist(workdir):
    with pytest.raises(FileNotFoundError):
        debocker.load_packages('focal', 'missing.{release}', True)


# release table

def test_releases_table():
    versions = set()
    for release,(distro,version,keys,eol) in debocker.releases.items():
        assert distro.lower() in debocker.eol_mirrors, release
        assert distro.lower() in debocker.keyring_packages, release
        assert keys in (debocker.KEYRING, debocker.REMOVED, debocker.UNSIGNED), release
        assert isinstance(eol, bool), release
        assert (distro, version) not in versions, release
        versions.add((distro, version))


# Let's Encrypt

CONF = 'mozilla/ACCVRAIZ1.crt\nmozilla/DST_Root_CA_X3.crt\nmozilla/ISRG_Root_X1.crt\n'


def test_install_certs(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(debocker, 'chroot', lambda *args, **kw: calls.append(args) or 0)
    (tmp_path / 'etc').mkdir()
    conf = tmp_path / 'etc' / 'ca-certificates.conf'
    conf.write_text(CONF)

    assert debocker.install_certs(str(tmp_path))
    assert debocker.install_certs(str(tmp_path))

    names = sorted(c.name for c in bundled('certs').iterdir() if c.name.endswith('.crt'))
    assert len(names) == 4
    lines = conf.read_text().splitlines()
    assert lines[:3] == ['mozilla/ACCVRAIZ1.crt', '!mozilla/DST_Root_CA_X3.crt', 'mozilla/ISRG_Root_X1.crt']
    assert lines[3:] == [f'letsencrypt/{n}' for n in names]
    for n in names:
        copied = tmp_path / 'usr' / 'share' / 'ca-certificates' / 'letsencrypt' / n
        assert copied.read_bytes() == bundled('certs').joinpath(n).read_bytes()
    assert calls == [(str(tmp_path), ['update-ca-certificates'])] * 2


def test_install_certs_without_ca_certificates(tmp_path, monkeypatch):
    monkeypatch.setattr(debocker, 'chroot', lambda *args, **kw: pytest.fail('chroot called'))
    assert not debocker.install_certs(str(tmp_path))


def test_install_certs_update_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(debocker, 'chroot', lambda *args, **kw: 1)
    (tmp_path / 'etc').mkdir()
    (tmp_path / 'etc' / 'ca-certificates.conf').write_text(CONF)
    assert not debocker.install_certs(str(tmp_path))


# updates

def make_rootfs(tmp_path, line):
    (tmp_path / 'etc' / 'apt').mkdir(parents=True)
    (tmp_path / 'usr' / 'sbin').mkdir(parents=True)
    (tmp_path / 'proc').mkdir()
    sources = tmp_path / 'etc' / 'apt' / 'sources.list'
    sources.write_text(line + '\n')
    return sources


@pytest.fixture
def fake_update(monkeypatch):
    # record chroot commands and the policy-rc.d seen while they run, and
    # pretend mounting failed so nothing is mounted
    seen = {'cmds': [], 'policy': [], 'update_output': 'Hit http://mirror Release\n'}

    def record(dest, cmd):
        seen['cmds'].append(cmd)
        policy = os.path.join(dest, 'usr', 'sbin', 'policy-rc.d')
        seen['policy'].append(open(policy).read() if os.path.exists(policy) else None)

    def chroot(dest, cmd, quiet):
        record(dest, cmd)
        return 0

    def chroot_output(dest, cmd):
        record(dest, cmd)
        return 0, seen['update_output']

    monkeypatch.setattr(debocker, 'chroot', chroot)
    monkeypatch.setattr(debocker, 'chroot_output', chroot_output)
    monkeypatch.setattr(debocker.subprocess, 'run',
        lambda *args, **kw: subprocess.CompletedProcess(args, 1))
    return seen


def test_update_release_ubuntu(tmp_path, monkeypatch, fake_update):
    url = 'http://old-releases.ubuntu.com/ubuntu'
    sources = make_rootfs(tmp_path, f'deb {url} precise main universe')
    monkeypatch.setattr(debocker, 'suite_exists', lambda mirror, suite: True)

    assert debocker.update_release(str(tmp_path), 'precise', 'ubuntu', True, True)
    assert sources.read_text().splitlines() == [
        f'deb {url} precise main universe',
        f'deb {url} precise-updates main universe',
        f'deb {url} precise-security main universe',
        ]
    assert [c[1] for c in fake_update['cmds']] == ['update', '-y', 'clean']
    assert fake_update['cmds'][1][-1] == 'dist-upgrade'
    assert fake_update['policy'] == ['#!/bin/sh\nexit 101\n'] * 3
    assert not (tmp_path / 'usr' / 'sbin' / 'policy-rc.d').exists()


def test_update_release_debian_security_fallback(tmp_path, monkeypatch, fake_update):
    url = 'http://archive.debian.org/debian'
    sources = make_rootfs(tmp_path, f'deb {url} jessie main contrib non-free')
    present = {(debocker.security_mirrors[True], 'jessie/updates')}
    monkeypatch.setattr(debocker, 'suite_exists', lambda mirror, suite: (mirror, suite) in present)

    assert debocker.update_release(str(tmp_path), 'jessie', 'debian', True, True)
    assert sources.read_text().splitlines() == [
        f'deb {url} jessie main contrib non-free',
        f'deb {debocker.security_mirrors[True]} jessie/updates main contrib non-free',
        ]


def test_update_release_debian_one_security_suite(tmp_path, monkeypatch, fake_update):
    sources = make_rootfs(tmp_path, 'deb http://deb.debian.org/debian bullseye main')
    monkeypatch.setattr(debocker, 'suite_exists', lambda mirror, suite: True)

    assert debocker.update_release(str(tmp_path), 'bullseye', 'debian', False, True)
    security = debocker.security_mirrors[False]
    assert sources.read_text().splitlines() == [
        'deb http://deb.debian.org/debian bullseye main',
        'deb http://deb.debian.org/debian bullseye-updates main',
        f'deb {security} bullseye-security main',
        ]


def test_update_release_keeps_existing_policy(tmp_path, monkeypatch, fake_update):
    make_rootfs(tmp_path, 'deb http://deb.debian.org/debian trixie main')
    policy = tmp_path / 'usr' / 'sbin' / 'policy-rc.d'
    policy.write_text('#!/bin/sh\nexit 0\n')
    monkeypatch.setattr(debocker, 'suite_exists', lambda mirror, suite: False)

    assert debocker.update_release(str(tmp_path), 'trixie', 'debian', False, True)
    assert policy.read_text() == '#!/bin/sh\nexit 0\n'


def test_update_release_stops_on_failure(tmp_path, monkeypatch, fake_update):
    make_rootfs(tmp_path, 'deb http://deb.debian.org/debian trixie main')
    monkeypatch.setattr(debocker, 'suite_exists', lambda mirror, suite: False)
    monkeypatch.setattr(debocker, 'chroot_output',
        lambda dest, cmd: fake_update['cmds'].append(cmd) or (100, 'E: failed\n'))

    assert not debocker.update_release(str(tmp_path), 'trixie', 'debian', False, True)
    assert fake_update['cmds'] == [['apt-get', 'update']]
    assert not (tmp_path / 'usr' / 'sbin' / 'policy-rc.d').exists()


@pytest.mark.parametrize('output', [
    'W: GPG error: http://archive.debian.org jessie Release: The following signatures were invalid: KEYEXPIRED 1587841717\n',
    "E: The repository 'http://archive.debian.org/debian buster Release' is no longer signed.\n",
    'E: Release file for http://archive.debian.org/debian-security/dists/buster/updates/InRelease is expired\n',
    ])
def test_update_release_allows_unauthenticated(tmp_path, monkeypatch, fake_update, output):
    make_rootfs(tmp_path, 'deb http://archive.debian.org/debian jessie main')
    monkeypatch.setattr(debocker, 'suite_exists', lambda mirror, suite: False)
    fake_update['update_output'] = output

    assert debocker.update_release(str(tmp_path), 'jessie', 'debian', True, True)
    conf = tmp_path / 'etc' / 'apt' / 'apt.conf.d' / '99debocker-unauthenticated'
    assert conf.read_text() == debocker.unauthenticated_conf
    assert 'APT::Get::AllowUnauthenticated "true";' in conf.read_text()
    assert [c[1] for c in fake_update['cmds']] == ['update', 'update', '-y', 'clean']


def test_update_release_authenticated(tmp_path, monkeypatch, fake_update):
    make_rootfs(tmp_path, 'deb http://deb.debian.org/debian trixie main')
    monkeypatch.setattr(debocker, 'suite_exists', lambda mirror, suite: False)

    assert debocker.update_release(str(tmp_path), 'trixie', 'debian', False, True)
    assert not (tmp_path / 'etc' / 'apt' / 'apt.conf.d').exists()
    assert [c[1] for c in fake_update['cmds']] == ['update', '-y', 'clean']


def test_update_release_mounts(tmp_path, monkeypatch, fake_update):
    make_rootfs(tmp_path, 'deb http://deb.debian.org/debian trixie main')
    monkeypatch.setattr(debocker, 'suite_exists', lambda mirror, suite: False)
    calls = []

    def run(cmd, *args, **kw):
        calls.append(cmd)
        # proc mounts, devpts fails
        return subprocess.CompletedProcess(cmd, 1 if 'devpts' in cmd else 0)

    monkeypatch.setattr(debocker.subprocess, 'run', run)
    assert debocker.update_release(str(tmp_path), 'trixie', 'debian', False, True)
    proc,pts = str(tmp_path / 'proc'), str(tmp_path / 'dev' / 'pts')
    assert calls == [
        ['mount', '-t', 'proc', 'proc', proc],
        ['mount', '-t', 'devpts', 'devpts', pts],
        ['umount', proc],
        ]
    assert os.path.isdir(pts)


# foreign architectures

@pytest.fixture
def host_amd64(monkeypatch):
    real_run = subprocess.run

    def run(cmd, *args, **kw):
        if cmd[0] == 'dpkg':
            return subprocess.CompletedProcess(cmd, 0, stdout='amd64\n')
        return real_run(cmd, *args, **kw)

    monkeypatch.setattr(debocker.subprocess, 'run', run)


def handler(binfmt, name, text):
    binfmt.mkdir(exist_ok=True)
    (binfmt / f'qemu-{name}').write_text(text)


def test_check_arch_native(tmp_path, host_amd64):
    assert debocker.check_arch('amd64', str(tmp_path))
    assert debocker.check_arch('i386', str(tmp_path))


def test_check_arch_handler(tmp_path, host_amd64):
    handler(tmp_path, 'aarch64', 'enabled\ninterpreter /usr/bin/qemu-aarch64-static\nflags: POCF\noffset 0\n')
    assert debocker.check_arch('arm64', str(tmp_path))


def test_check_arch_missing_handler(tmp_path, host_amd64):
    assert not debocker.check_arch('arm64', str(tmp_path))


def test_check_arch_needs_fix_binary_flag(tmp_path, host_amd64):
    handler(tmp_path, 'aarch64', 'enabled\ninterpreter /usr/bin/qemu-aarch64\nflags: OC\n')
    assert not debocker.check_arch('arm64', str(tmp_path))


def test_check_arch_disabled(tmp_path, host_amd64):
    handler(tmp_path, 'aarch64', 'disabled\ninterpreter /usr/bin/qemu-aarch64-static\nflags: F\n')
    assert not debocker.check_arch('arm64', str(tmp_path))


def test_check_arch_unknown(tmp_path, host_amd64):
    assert not debocker.check_arch('vax', str(tmp_path))


# partial builds

def test_mounts_under(tmp_path):
    mounts = tmp_path / 'mounts'
    mounts.write_text(
        'proc /build/x.partial/proc proc rw 0 0\n'
        'devpts /build/x.partial/dev/pts devpts rw 0 0\n'
        'tmpfs /build/x.partial2 tmpfs rw 0 0\n'
        'tmpfs /build/with\\040space tmpfs rw 0 0\n'
        'proc /proc proc rw 0 0\n')
    assert debocker.mounts_under('/build/x.partial', str(mounts)) == [
        '/build/x.partial/proc', '/build/x.partial/dev/pts']
    assert debocker.mounts_under('/build/with space', str(mounts)) == ['/build/with space']
    assert debocker.mounts_under('/elsewhere', str(mounts)) == []


# image contents

def test_tar_command_excludes(tmp_path):
    root = tmp_path / 'root'
    for path in [
        'etc/resolv.conf', 'etc/hostname', 'etc/hosts',
        'var/cache/apt/archives/foo_1.0_amd64.deb', 'var/cache/apt/archives/lock',
        'var/lib/apt/lists/archive.ubuntu.com_ubuntu_dists_focal_InRelease',
        'var/lib/apt/lists/lock', 'bin/sh',
        ]:
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text('x')
    (root / 'var/cache/apt/archives/partial').mkdir()
    (root / 'var/lib/apt/lists/partial').mkdir()

    out = tmp_path / 'image.tar'
    with open(out, 'wb') as fp:
        subprocess.run(debocker.tar_command(str(root)), stdout=fp, check=True)
    with tarfile.open(out) as tf:
        names = {n.lstrip('./').rstrip('/') for n in tf.getnames()} - {''}

    assert names >= {
        'etc/hosts', 'bin/sh', 'var/lib/apt/lists/partial', 'var/lib/apt/lists/lock',
        'var/cache/apt/archives/partial', 'var/cache/apt/archives/lock',
        }
    assert not names & {
        'etc/resolv.conf', 'etc/hostname',
        'var/cache/apt/archives/foo_1.0_amd64.deb',
        'var/lib/apt/lists/archive.ubuntu.com_ubuntu_dists_focal_InRelease',
        }


def test_tar_command_numeric_owner():
    assert '--numeric-owner' in debocker.tar_command('/x')


# command line

def test_main_lists_releases(capsys, monkeypatch):
    monkeypatch.setattr('sys.argv', ['debocker', '?'])
    assert debocker.main() == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == len(debocker.releases)
    assert out[0].startswith('hardy')


def test_main_unknown_release(capsys, monkeypatch):
    monkeypatch.setattr('sys.argv', ['debocker', 'nope'])
    assert debocker.main() == 1
    assert '[!] unknown release: nope' in capsys.readouterr().out


def test_main_passes_options(monkeypatch):
    seen = {}
    monkeypatch.setattr(debocker, 'build', lambda **kw: seen.update(kw) or 0)
    monkeypatch.setattr('sys.argv', ['debocker', '-a', 'arm64', '-e', '-U', '-q', 'focal', 'http://m'])
    assert debocker.main() == 0
    assert seen == {
        'release': 'focal', 'mirror': 'http://m', 'arch': 'arm64', 'packages': None,
        'letsencrypt': False, 'updates': False, 'quiet': True,
        }
