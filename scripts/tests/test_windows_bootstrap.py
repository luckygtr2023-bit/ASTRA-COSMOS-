"""Portable regression checks, NOT Windows runtime verification.
Run: python -m unittest discover -s scripts/tests -v
"""
import importlib.util
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PS = (ROOT / 'scripts/start_astra.ps1').read_text(encoding='utf-8-sig')
BAT = (ROOT / 'START.bat').read_text()
spec = importlib.util.spec_from_file_location('dependency_check', ROOT / 'scripts/check_python_dependencies.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class BootstrapStaticTests(unittest.TestCase):
    def test_root_and_retention(self):
        self.assertIn('cd /d "%~dp0"', BAT)
        self.assertIn('DisableDelayedExpansion', BAT)
        self.assertIn('-NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\start_astra.ps1"', BAT)
        self.assertIn('Set-Location -LiteralPath $root', PS)
        self.assertIn("Read-Host 'Press ENTER", PS)
        self.assertNotIn('%*', BAT)

    def test_no_legacy_launcher_or_download_execution(self):
        self.assertNotIn('ASTRA COSMOS.exe', PS)
        for forbidden in ('Invoke-Expression', 'Invoke-WebRequest', '-Verb RunAs', 'Set-ExecutionPolicy'):
            self.assertNotIn(forbidden, PS + BAT)
        self.assertIn("'--index-url', 'https://pypi.org/simple'", PS)

    def test_process_diagnostics_not_fake_ready(self):
        for required in ('ReadLineAsync()', 'PROCESS_CREATED', '$process.ExitCode', 'Last startup stage', 'Protect-Text'):
            self.assertIn(required, PS)
        self.assertNotIn('has started successfully', PS)
        self.assertNotIn('ASTRA launched successfully', PS)
        self.assertIn('without establishing a persistent application', PS)

    def test_process_only_policy_and_bootstrap_diagnostics(self):
        self.assertEqual(BAT.count('-ExecutionPolicy Bypass'), 1)
        self.assertNotIn('-NoExit', BAT)  # Host failures return immediately to batch pause.
        self.assertIn('set "ASTRA_EXIT=%ERRORLEVEL%"', BAT)
        self.assertIn('[ASTRA📡🌌] STARTUP FAILED', BAT)
        self.assertIn('The actual PowerShell error is shown above.', BAT)
        self.assertIn("Say 'PowerShell bootstrap started.'", PS)
        self.assertIn("Say 'Checking dependencies...'", PS)
        for forbidden in ('Set-ExecutionPolicy', '-Scope LocalMachine', '-Scope CurrentUser', '-Verb RunAs'):
            self.assertNotIn(forbidden, BAT + PS)

    def test_explicit_headless_only(self):
        self.assertIn("if ($Headless) { $info.Arguments = '--headless' }", PS)
        self.assertNotIn('-Headless', BAT)

    def test_pe_and_vulkan_checks(self):
        for required in ('0x5A4D', '0x4550', '0x8664', '0x2000', 'LoadLibraryEx', 'SystemDirectory', 'GPU rendering NOT VERIFIED'):
            self.assertIn(required, PS)

    def test_existing_packaged_target_is_elf(self):
        path = ROOT / 'release/ASTRA-COSMOS/bin/astra_native'
        self.assertEqual(path.read_bytes()[:4], b'\x7fELF')
        data = (ROOT / 'ASTRA COSMOS.exe').read_bytes()
        self.assertEqual(data[:2], b'MZ')
        offset = struct.unpack_from('<I', data, 60)[0]
        self.assertEqual(data[offset:offset+4], b'PE\0\0')

    def test_declared_dependencies_reused(self):
        versions = {'astra-core': '0.1.1', 'supabase': '2.0', 'python-dotenv': '1.0', 'httpx': '0.24'}
        with patch.object(checker.metadata, 'version', side_effect=versions.__getitem__), patch.object(checker.metadata, 'requires', return_value=['supabase>=2.0', 'python-dotenv>=1.0', 'httpx>=0.24']):
            self.assertEqual(checker.main(), 0)

    def test_missing_package_requests_install(self):
        with patch.object(checker.metadata, 'version', side_effect=checker.metadata.PackageNotFoundError):
            self.assertEqual(checker.main(), 1)

    def test_changed_declaration_requests_install(self):
        with patch.object(checker.metadata, 'version', return_value='0.1.1'), patch.object(checker.metadata, 'requires', return_value=[]):
            self.assertEqual(checker.main(), 1)

    def test_encoding(self):
        self.assertTrue((ROOT / 'scripts/start_astra.ps1').read_bytes().startswith(b'\xef\xbb\xbf'))
        self.assertIn(b'\r\n', (ROOT / 'START.bat').read_bytes())


if __name__ == '__main__':
    unittest.main()
