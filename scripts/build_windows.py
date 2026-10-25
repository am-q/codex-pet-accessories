"""Build and verify a Windows x64 portable ZIP and its source archive."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def dependency_licenses():
    files = {'licenses/Python-LICENSE.txt': Path(sys.base_prefix) / 'LICENSE.txt'}
    for library in ('tcl8.6', 'tk8.6'):
        files[f'licenses/{library}-license.terms'] = Path(sys.base_prefix) / 'tcl' / library / 'license.terms'
    if not files['licenses/tcl8.6-license.terms'].is_file():
        files['licenses/tcl8.6-license.terms'] = ROOT / 'licenses/Tcl-license.terms'
    for package in ('Pillow', 'pyinstaller', 'pyinstaller-hooks-contrib', 'altgraph',
                    'packaging', 'pefile', 'pywin32-ctypes', 'setuptools'):
        distribution = importlib.metadata.distribution(package)
        for name in distribution.files or ():
            if any(word in name.name.lower() for word in ('license', 'copying', 'notice')):
                path = Path(distribution.locate_file(name))
                if path.is_file():
                    files[f'licenses/{package}/{name.as_posix()}'] = path
    for name, path in files.items():
        if not path.is_file():
            raise RuntimeError(f'Missing dependency license: {name}')
    return files


def main():
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('Build on 64-bit Windows with 64-bit Python')
    subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/package_release.py')], cwd=ROOT, check=True)
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    build = ROOT / 'build' / 'portable'
    for name in ('exe', 'work', 'spec', 'config'):
        (build / name).mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment['PYINSTALLER_CONFIG_DIR'] = str(build / 'config')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
               '--windowed', '--noupx', '--name', 'CodexPetAccessories',
               '--distpath', str(build / 'exe'), '--workpath', str(build / 'work'),
               '--specpath', str(build / 'spec'), '--paths', str(ROOT / 'src'),
               '--add-data', str(ROOT / 'src/pet_lifecycle_task.ps1') + ':.',
               '--add-data', str(ROOT / 'VERSION') + ':.', str(ROOT / 'src/pet_base.py')]
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
    executable = build / 'exe' / 'CodexPetAccessories.exe'
    archive = ROOT / 'dist' / f'codex-pet-accessories-{version}-windows-x64.zip'
    prefix = f'codex-pet-accessories-{version}-windows-x64'
    files = {'CodexPetAccessories.exe': executable, 'LICENSE.txt': ROOT / 'LICENSE',
             'THIRD_PARTY_NOTICES.md': ROOT / 'THIRD_PARTY_NOTICES.md', **dependency_licenses()}
    chinese = ('Codex 宠物用量配件 ' + version + '\n\n'
               '1. 把 ZIP 完整解压到一个文件夹。\n'
               '2. 打开并登录 Codex，显示桌面宠物。\n'
               '3. 双击 CodexPetAccessories.exe。无需安装 Python。\n'
               '4. 点击或右键配件调整外观；从菜单退出。\n\n'
               '启用自动启停后请保留程序文件夹的位置；移动前先关闭该开关。\n'
               '本包只包含用量配件，不安装或替换宠物。\n'
               '完整说明：https://github.com/am-q/codex-pet-accessories\n')
    english = (f'Codex Pet Accessories {version}\n\n'
               '1. Extract the complete ZIP to a folder.\n'
               '2. Open Codex, sign in, and show your desktop pet.\n'
               '3. Double-click CodexPetAccessories.exe. Python is not required.\n'
               '4. Click or right-click an accessory for settings; exit from its menu.\n\n'
               'Keep the application folder in place when automatic startup is enabled.\n'
               'Disable that option before moving the application.\n'
               'This package does not install or replace a pet.\n'
               'Guide: https://github.com/am-q/codex-pet-accessories/blob/main/README.en.md\n')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for name, path in sorted(files.items()):
            output.write(path, f'{prefix}/{name}')
        output.writestr(f'{prefix}/READ_ME_中文.txt', chinese.encode('utf-8-sig'))
        output.writestr(f'{prefix}/READ_ME_English.txt', english.encode('utf-8-sig'))
    subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/verify_portable.py'), str(archive)],
                   cwd=ROOT, check=True)
    source = ROOT / 'dist' / f'codex-pet-accessories-{version}-source.zip'
    sums = ROOT / 'dist' / 'SHA256SUMS.txt'
    sums.write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n'
                            for path in (archive, source)), encoding='ascii')
    print(json.dumps({'portable_zip': archive.name, 'source_zip': source.name,
                      'version': version, 'bytes': archive.stat().st_size,
                      'verification': 'passed'}))


if __name__ == '__main__':
    main()
