"""Portable release POLICY tests, not C# execution or Windows/GPU tests.
Synthetic PE headers exist only inside temporary test archives; not deployable EXEs.
"""
import importlib.util
import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('release_tools', ROOT / 'distribution/release_tools.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def pe(machine=0x8664, dll=False):
    data = bytearray(256)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 128)
    struct.pack_into('<4sH', data, 128, b'PE\0\0', machine)
    struct.pack_into('<HH', data, 150, 2 | (0x2000 if dll else 0), 0x20b)
    return bytes(data)


class ReleasePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.zip = Path(self.temp.name) / 'runtime.zip'

    def archive(self, entries=None):
        with zipfile.ZipFile(self.zip, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in entries or [(release.ENTRY, pe()), ('shaders/scene.spv', b'test-only-not-shader')]:
                archive.writestr(name, content)
        return self.zip

    def catalog(self):
        return {'schema': 1, 'state': 'ready', 'version': '1.2.3',
                'url': f'{release.REPO}/v1.2.3/{release.ASSET}', 'size': self.zip.stat().st_size,
                'sha256': release.digest(self.zip), 'entryPoint': release.ENTRY, 'python': 'none',
                'files': release.inspect_archive(self.zip)}

    def test_well_formed_test_inventory(self):
        self.archive()
        release.verify_archive(self.zip, self.catalog())

    def test_blocked_catalog_shipped(self):
        with self.assertRaisesRegex(ValueError, 'BLOCKED'):
            release.validate_catalog(json.loads((ROOT / 'bootstrap/release.json').read_text()))

    def test_unsafe_paths(self):
        for name in ('../bad.exe', '/bad.exe', 'C:/bad.exe', 'a\\b', 'a/../b', 'a//b', 'a/b.', 'a/b ', 'a/CON.txt', 'NUL', 'COM1.exe', 'a:b', 'a/\x00b', 'a/\nb', 'a/é', 'a/../ASTRA COSMOS.exe', '.env', '.env.local', '.git/config'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                release.safe_path(name)

    def test_case_collisions(self):
        self.archive([(release.ENTRY, pe()), ('asset.bin', b'a'), ('ASSET.bin', b'b')])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            release.inspect_archive(self.zip)

    def test_file_directory_collision(self):
        self.archive([(release.ENTRY, pe()), ('assets', b'a'), ('assets/a.bin', b'b')])
        with self.assertRaisesRegex(ValueError, 'collision'):
            release.inspect_archive(self.zip)

    def test_symlink(self):
        link = zipfile.ZipInfo('assets/link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.archive([(release.ENTRY, pe()), (link, b'../../outside')])
        with self.assertRaisesRegex(ValueError, 'Links'):
            release.inspect_archive(self.zip)

    def test_windows_reparse_point(self):
        link = zipfile.ZipInfo('assets/reparse')
        link.external_attr = 0x400
        self.archive([(release.ENTRY, pe()), (link, b'data')])
        with self.assertRaisesRegex(ValueError, 'Links'):
            release.inspect_archive(self.zip)

    def test_directory_entries_rejected(self):
        self.archive([(release.ENTRY, pe()), ('assets/', b'')])
        with self.assertRaises(ValueError):
            release.inspect_archive(self.zip)

    def test_development_tools_and_scripts_rejected(self):
        for name in ('tools/cmake.exe', 'MSBuild.exe', 'cl.exe', 'git.exe', 'vulkaninfo.exe', 'glslangValidator.exe', 'pip.exe', 'run.bat', 'start.CMD', 'install.ps1', 'app.lnk'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                release.safe_path(name)

    def test_corrupted_archive_hash(self):
        self.archive()
        catalog = self.catalog()
        catalog['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'checksum'):
            release.verify_archive(self.zip, catalog)

    def test_per_file_hash(self):
        self.archive()
        catalog = self.catalog()
        catalog['files'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'inventory'):
            release.verify_archive(self.zip, catalog)

    def test_archive_missing_executable(self):
        self.archive([('asset.json', b'{}')])
        with self.assertRaisesRegex(ValueError, 'entry point'):
            release.inspect_archive(self.zip)

    def test_elf_not_windows(self):
        self.archive([(release.ENTRY, b'\x7fELF' + bytes(252))])
        with self.assertRaisesRegex(ValueError, 'Not Windows PE'):
            release.inspect_archive(self.zip)

    def test_wrong_architecture_and_dll_exe(self):
        for content in (pe(0x14c), pe(dll=True)):
            self.archive([(release.ENTRY, content)])
            with self.assertRaises(ValueError):
                release.inspect_archive(self.zip)

    def test_missing_acceptance_not_promoted(self):
        self.archive()
        evidence = json.loads((ROOT / 'distribution/acceptance.template.json').read_text())
        evidence['runtime_sha256'] = release.digest(self.zip)
        with self.assertRaisesRegex(ValueError, 'acceptance'):
            release.evidence_gate(evidence, self.zip, ROOT)

    def test_current_mock_main_blocks_even_claimed_acceptance(self):
        self.archive()
        evidence = {'runtime_sha256': release.digest(self.zip), 'checks': {key: 'VERIFIED' for key in release.EVIDENCE_CHECKS}, **{key: 'synthetic-test' for key in ('reviewer', 'source_commit', 'gpu_name', 'vulkan_version', 'test_record')}}
        with self.assertRaisesRegex(ValueError, 'diagnostic runtime'):
            release.evidence_gate(evidence, self.zip, ROOT)

    def test_untrusted_urls_and_versions(self):
        self.archive()
        for url in ('http://github.com/a', 'https://evil.example/a', f'{release.REPO}/v0.0.1/{release.ASSET}', f'{release.REPO}/v1.2.3/{release.ASSET}?token=x'):
            catalog = self.catalog()
            catalog['url'] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                release.validate_catalog(catalog)
        for version in ('latest', '../1.0.0', '01.2.3', '1.2.3;run'):
            catalog = self.catalog()
            catalog['version'] = version
            with self.subTest(version=version), self.assertRaises(ValueError):
                release.validate_catalog(catalog)

    def test_no_user_build_chain(self):
        bat = (ROOT / 'START.bat').read_text()
        self.assertNotIn('terminal.bat', bat)
        for tool in ('powershell.exe', 'cmake.exe', 'python.exe', 'pip install', 'git.exe', 'dotnet'):
            self.assertNotIn(tool, bat.lower())
        self.assertIn('".\\ASTRA COSMOS.exe"', bat)

    def test_source_offline_and_transaction_guards(self):
        program = (ROOT / 'bootstrap/src/Program.cs').read_text()
        installer = (ROOT / 'bootstrap/src/Installer.cs').read_text()
        self.assertIn('installed != null && !args.Contains("--update")', program)
        self.assertIn('FileShare.None', program)
        self.assertIn('if (commit) Installer.Commit', program)
        self.assertIn('previous.json', installer)
        self.assertIn('File.Replace', installer)
        self.assertIn('AllowAutoRedirect = false', installer)
        self.assertIn('Policy.Digest(zip) != release.Sha256', installer)
        self.assertIn('FileMode.CreateNew', installer)
        self.assertIn('Runtime did not establish readiness', program)
        # These inspect source structure, not C# runtime semantics.


if __name__ == '__main__':
    unittest.main()
