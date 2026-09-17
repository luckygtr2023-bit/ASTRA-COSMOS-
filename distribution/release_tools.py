"""Build-machine-only release inspection. Never shipped as an end-user prerequisite.
No network requests, source compilation, installer execution or secret handling.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import zipfile

REPO = "https://github.com/luckygtr2023-bit/ASTRA-COSMOS-/releases/download"
ASSET = "ASTRA-Windows-x64-Runtime.zip"
ENTRY = "ASTRA COSMOS.exe"
MAX_ARCHIVE = 4 * 1024**3
MAX_EXPANDED = 12 * 1024**3
MAX_FILES = 50000
FORBIDDEN = {x.lower() for x in ("cmake.exe", "msbuild.exe", "cl.exe", "ninja.exe", "git.exe", "vulkaninfo.exe", "glslangvalidator.exe", "glslc.exe", "pip.exe", "conan.exe", "vcpkg.exe")}
EVIDENCE_CHECKS = ("windows_x64_release_build", "real_window", "real_vulkan", "actual_gpu", "valid_shaders_assets", "scientific_engine_connected", "persistent_render_loop", "clean_shutdown", "dll_dependency_audit", "clean_machine_without_tools", "offline_second_launch", "readiness_protocol_v1", "userdata_outside_runtime")


def digest(path: Path) -> str:
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def safe_path(name: str) -> None:
    if not isinstance(name, str) or not name or len(name) > 200 or '\\' in name or name.startswith('/'):
        raise ValueError('Unsafe archive path')
    for part in name.split('/'):
        if not part or part in ('.', '..') or part.endswith(('.', ' ')) or any(ord(c) < 32 or ord(c) > 126 or c in ':<>"|?*' for c in part):
            raise ValueError('Unsafe Windows path component')
        if part.lower() in ('.git', '.env') or part.lower().startswith('.env.'):
            raise ValueError('Repository credentials/environment files must not be packaged')
        if re.fullmatch(r'CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9]', part.split('.')[0], re.I):
            raise ValueError('Reserved Windows filename')
    base = name.split('/')[-1].lower()
    if base in FORBIDDEN or PurePosixPath(base).suffix in ('.bat', '.cmd', '.ps1', '.lnk', '.url'):
        raise ValueError('Build tool or executable script in runtime payload')


def check_pe(data: bytes, name: str) -> None:
    if len(data) < 256 or data[:2] != b'MZ':
        raise ValueError('Not Windows PE: ' + name)
    offset = struct.unpack_from('<I', data, 60)[0]
    if offset > len(data) - 26:
        raise ValueError('Invalid PE header: ' + name)
    signature, machine = struct.unpack_from('<4sH', data, offset)
    flags, magic = struct.unpack_from('<HH', data, offset + 22)
    if signature != b'PE\0\0' or machine != 0x8664 or magic != 0x20b or not flags & 2:
        raise ValueError('Not x64 PE32+: ' + name)
    if name.lower().endswith('.exe') and flags & 0x2000:
        raise ValueError('DLL presented as executable: ' + name)


def inspect_archive(path: Path) -> list[dict]:
    if not 0 < path.stat().st_size <= MAX_ARCHIVE:
        raise ValueError('Runtime ZIP outside size limit')
    inventory, paths, total = [], set(), 0
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if not 0 < len(entries) <= MAX_FILES:
            raise ValueError('Invalid file count')
        for entry in entries:
            safe_path(entry.filename)
            key = entry.filename.lower()
            if key in paths:
                raise ValueError('Case-insensitive duplicate')
            paths.add(key)
            kind = stat.S_IFMT(entry.external_attr >> 16)
            if kind not in (0, stat.S_IFREG) or entry.external_attr & 0x400:
                raise ValueError('Links, directory entries and special files prohibited')
            if entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError('Encrypted or unsupported compressed archive')
            total += entry.file_size
            if total > MAX_EXPANDED:
                raise ValueError('Expanded archive outside size limit')
            # Stream/bound the contents; do not trust only ZIP metadata.
            checksum = hashlib.sha256()
            actual = 0
            header = bytearray()
            with archive.open(entry) as file:
                while chunk := file.read(128 * 1024):
                    actual += len(chunk)
                    if actual > entry.file_size:
                        raise ValueError('Uncompressed data exceeds declared size')
                    checksum.update(chunk)
                    # PE headers are normally small; reject files with offsets beyond this bound.
                    if len(header) < 1024 * 1024:
                        header.extend(chunk[:1024 * 1024 - len(header)])
            if actual != entry.file_size:
                raise ValueError('Truncated payload')
            if PurePosixPath(entry.filename).suffix.lower() in ('.exe', '.dll', '.pyd'):
                check_pe(header, entry.filename)
            inventory.append({'path': entry.filename, 'size': actual, 'sha256': checksum.hexdigest()})
    if ENTRY.lower() not in paths or not any(f['path'] == ENTRY for f in inventory):
        raise ValueError('Exact application entry point missing')
    for path in paths:
        parts = path.split('/')
        if any('/'.join(parts[:i]) in paths for i in range(1, len(parts))):
            raise ValueError('File/directory collision')
    return sorted(inventory, key=lambda f: f['path'])


def validate_catalog(catalog: dict) -> None:
    if catalog.get('schema') != 1:
        raise ValueError('Unsupported catalog schema')
    if catalog.get('state') == 'blocked':
        raise ValueError('Release BLOCKED: no verified production runtime published')
    version = catalog.get('version', '')
    if catalog.get('state') != 'ready' or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('Invalid release version/state')
    if catalog.get('url') != f'{REPO}/v{version}/{ASSET}':
        raise ValueError('Untrusted/mismatched release URL')
    if not re.fullmatch('[a-f0-9]{64}', catalog.get('sha256', '')) or not 0 < catalog.get('size', 0) <= MAX_ARCHIVE:
        raise ValueError('Invalid archive size/checksum')
    if catalog.get('entryPoint') != ENTRY or catalog.get('python') not in ('none', 'embedded'):
        raise ValueError('Invalid runtime entry point/Python strategy')
    records = catalog.get('files', [])
    if not 0 < len(records) <= MAX_FILES:
        raise ValueError('Invalid file inventory')
    paths, total = set(), 0
    for f in records:
        safe_path(f['path'])
        if f['path'].lower() in paths or not isinstance(f['size'], int) or f['size'] < 0 or not re.fullmatch('[a-f0-9]{64}', f['sha256']):
            raise ValueError('Invalid inventory entry')
        paths.add(f['path'].lower())
        total += f['size']
    if total > MAX_EXPANDED or not any(f['path'] == ENTRY for f in records):
        raise ValueError('Incomplete or excessive payload')
    for path in paths:
        parts = path.split('/')
        if any('/'.join(parts[:i]) in paths for i in range(1, len(parts))):
            raise ValueError('File/directory collision')


def verify_archive(path: Path, catalog: dict) -> None:
    validate_catalog(catalog)
    if path.stat().st_size != catalog['size'] or digest(path) != catalog['sha256']:
        raise ValueError('Archive checksum/size mismatch')
    actual = inspect_archive(path)
    if actual != sorted(catalog['files'], key=lambda f: f['path']):
        raise ValueError('Extracted inventory mismatch')


def evidence_gate(evidence: dict, runtime: Path, source: Path) -> None:
    # Attestations are release-review inputs, not automatically inferred GPU proof.
    if evidence.get('runtime_sha256') != digest(runtime):
        raise ValueError('Evidence is not tied to this archive')
    if any(evidence.get('checks', {}).get(check) != 'VERIFIED' for check in EVIDENCE_CHECKS):
        raise ValueError('Production acceptance gates are BLOCKED/NOT VERIFIED')
    for field in ('reviewer', 'source_commit', 'gpu_name', 'vulkan_version', 'test_record'):
        if not evidence.get(field):
            raise ValueError('Missing release evidence: ' + field)
    # Extra fail-closed guard for this checkout's confirmed diagnostic entry point.
    main = (source / 'native_renderer/src/main.cpp').read_text()
    if re.search(r'for\s*\(\s*int\s+i\s*=\s*0\s*;\s*i\s*<\s*120', main):
        raise ValueError('Current native main is the known finite diagnostic runtime; cannot publish it')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check')
    check.add_argument('catalog', type=Path)
    check.add_argument('--runtime', type=Path)
    make = sub.add_parser('catalog')
    make.add_argument('--runtime', type=Path, required=True)
    make.add_argument('--version', required=True)
    make.add_argument('--evidence', type=Path, required=True)
    make.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    make.add_argument('--python', choices=['none', 'embedded'], required=True)
    make.add_argument('--output', type=Path, required=True)
    bundle = sub.add_parser('bootstrap-zip')
    bundle.add_argument('--runtime', type=Path, required=True)
    bundle.add_argument('--catalog', type=Path, required=True)
    bundle.add_argument('--host', type=Path, required=True)
    bundle.add_argument('--evidence', type=Path, required=True)
    bundle.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    bundle.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'check':
            catalog = json.loads(args.catalog.read_text())
            validate_catalog(catalog)
            if args.runtime:
                verify_archive(args.runtime, catalog)
        elif args.command == 'bootstrap-zip':
            catalog = json.loads(args.catalog.read_text())
            verify_archive(args.runtime, catalog)
            evidence_gate(json.loads(args.evidence.read_text()), args.runtime, args.source)
            with args.host.open('rb') as host:
                check_pe(host.read(1024 * 1024), ENTRY)
            # Keep build tools and the source repository out of the end-user download.
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(args.host, ENTRY)
                archive.write(args.catalog, 'bootstrap/release.json')
                archive.write(args.source / 'START.bat', 'START.bat')
            args.output.with_suffix('.zip.sha256').write_text(digest(args.output) + '  ' + args.output.name + '\n')
            print('Bootstrap ZIP assembled. Signing and Windows install/launch verification are separate release gates.')
        else:
            evidence_gate(json.loads(args.evidence.read_text()), args.runtime, args.source)
            catalog = {'schema': 1, 'state': 'ready', 'version': args.version,
                       'url': f'{REPO}/v{args.version}/{ASSET}', 'size': args.runtime.stat().st_size,
                       'sha256': digest(args.runtime), 'entryPoint': ENTRY, 'python': args.python,
                       'files': inspect_archive(args.runtime)}
            validate_catalog(catalog)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(catalog, indent=2) + '\n')
        print('VERIFIED: catalog policy' + (' and archive integrity/structure' if getattr(args, 'runtime', None) else '') + '. This is not GPU/runtime verification.')
        return 0
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as error:
        print('BLOCKED:', error)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
