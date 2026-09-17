"""Portable BAT source/helper tests. These DO NOT execute Windows CMD.
Run: python -m unittest discover -s scripts/tests -v
"""
import importlib.util
from pathlib import Path
import re
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
BAT = (ROOT / 'START.bat').read_text()
TERMINAL = (ROOT / 'scripts/terminal.bat').read_text()
spec = importlib.util.spec_from_file_location('dependency_check', ROOT / 'scripts/check_python_dependencies.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class BootstrapStaticTests(unittest.TestCase):
    def test_root_discovery_and_no_call_path_reexpansion(self):
        self.assertIn('set "ASTRA_ROOT=%~dp0"', BAT)
        self.assertIn('cd /d "%ASTRA_ROOT%"', BAT)
        self.assertIn('call scripts\\terminal.bat', BAT)
        self.assertIn('cd /d "%~dp0.."', TERMINAL)
        self.assertNotIn('%*', BAT)
        for text in (BAT, TERMINAL):
            self.assertIn('DisableDelayedExpansion', text)
            for line in text.splitlines():
                if line.lower().startswith('call '):
                    self.assertNotIn('%', line)

    def test_no_powershell_or_policy_dependency(self):
        for token in ('powershell', '.ps1', 'executionpolicy', 'runas'):
            self.assertNotIn(token, (BAT + TERMINAL).lower())
        self.assertFalse((ROOT / 'scripts/start_astra.ps1').exists())

    def test_every_label_reference_exists(self):
        for text in (BAT, TERMINAL):
            labels = set(re.findall(r'^:([a-z_]+)', text, re.M | re.I))
            references = re.findall(r'\bgoto ([a-z_]+)|\bcall :([a-z_]+)', text, re.I)
            for pair in references:
                self.assertIn(next(item for item in pair if item), labels)

    def test_error_retention_and_result_capture(self):
        for text in (BAT, TERMINAL):
            self.assertIn('STARTUP FAILED', text)
            self.assertIn('Stage:', text)
            self.assertIn('Error:', text)
            self.assertIn('Exit code:', text)
            self.assertIn('pause', text)
        self.assertIn('"%ASTRA_NATIVE%" %ASTRA_ARGUMENTS%\nset "ASTRA_CODE=%ERRORLEVEL%"', TERMINAL)
        self.assertIn('exit /b %ASTRA_CODE%', TERMINAL)

    def test_dependencies_are_optional_and_declared(self):
        self.assertIn('if "%ASTRA_SETUP%"=="0" goto python_optional', TERMINAL)
        self.assertIn('check_python_dependencies.py', TERMINAL)
        self.assertIn('-m pip --isolated install --index-url https://pypi.org/simple -e .', TERMINAL)
        self.assertIn('if exist ".venv\\" goto invalid_venv', TERMINAL)
        self.assertIn('if exist "venv\\" goto invalid_venv', TERMINAL)
        self.assertNotIn('activate.bat', TERMINAL)

    def test_native_target_and_explicit_headless(self):
        self.assertIn('--target astra_native', TERMINAL)
        self.assertIn('-DASTRA_BUILD_LAUNCHER=OFF', TERMINAL)
        self.assertNotIn('ASTRA COSMOS.exe', BAT + TERMINAL)
        self.assertIn('if "%ASTRA_HEADLESS%"=="1" set "ASTRA_ARGUMENTS=--headless"', TERMINAL)
        self.assertNotIn('--headless', BAT)
        self.assertIn('Windows loader will validate executable format', TERMINAL)

    def test_no_fake_success_or_gpu_claim(self):
        self.assertIn('GPU rendering NOT VERIFIED by CMD', TERMINAL)
        self.assertIn('Native exit code was 0 but persistent application readiness was not established', TERMINAL)
        self.assertNotIn('has started successfully', TERMINAL)
        self.assertNotIn('ASTRA📡🌌 RUNNING', TERMINAL)

    def test_curated_logging_not_secret_output(self):
        self.assertIn('logs\\astra_startup.log', TERMINAL)
        self.assertIn('[%DATE% %TIME%] [%ASTRA_STAGE%]', TERMINAL)
        self.assertNotIn('2>&1', TERMINAL)
        self.assertNotIn('type ".env"', TERMINAL.lower())
        self.assertNotIn('set >>', TERMINAL.lower())
        self.assertNotIn('"%ASTRA_NATIVE%" %ASTRA_ARGUMENTS% >>', TERMINAL)

    def test_launcher_deletions_preserve_runtime(self):
        self.assertFalse((ROOT / 'ASTRA COSMOS.exe').exists())
        self.assertFalse((ROOT / 'release/ASTRA-COSMOS/ASTRA COSMOS.exe').exists())
        self.assertTrue((ROOT / 'native_renderer/launcher/launcher.cpp').exists())
        self.assertTrue((ROOT / 'native_renderer/src/main.cpp').exists())
        self.assertEqual((ROOT / 'release/ASTRA-COSMOS/bin/astra_native').read_bytes()[:4], b'\x7fELF')

    def test_encoding(self):
        for relative in ('START.bat', 'scripts/terminal.bat'):
            data = (ROOT / relative).read_bytes()
            self.assertFalse(data.startswith(b'\xef\xbb\xbf'))
            self.assertNotIn(b'\n', data.replace(b'\r\n', b''))
            self.assertIn('chcp 65001 >nul', data.decode())

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


if __name__ == '__main__':
    unittest.main()
