"""Build a source-only archive from an explicit publishable file allowlist."""
from pathlib import Path
import re
import zipfile
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATIC = [
    'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'CHANGELOG.md', 'VERSION',
    'requirements.txt', 'Install.ps1', 'Launch.vbs', 'Stop.vbs', '.gitignore',
    '.gitattributes', '.github/workflows/tests.yml', 'examples/settings.example.json',
    'docs/DEVELOPMENT.md', 'docs/RELEASING.md', 'docs/HANDOFF.md', 'docs/styles.png',
    'scripts/verify_alpha_recovery.py', 'scripts/verify_windows.py', 'scripts/verify_menu_scaling.py', 'scripts/verify_dpi_stability.py',
    'scripts/package_release.py', 'src/pet_lifecycle_task.ps1',
    'scripts/verify_window_stack.py', 'scripts/verify_lifecycle_windows.py',
]


def release_files(root=ROOT):
    files=[root/name for name in STATIC]
    files+=sorted((root/'src').glob('*.py'))
    files+=sorted((root/'tests').glob('test_*.py'))
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing or symbolic-link release file: {path.name}')
        path.resolve().relative_to(root.resolve())
    return files


def main():
    subprocess.run([sys.executable, str(ROOT/'scripts/verify_windows.py')],cwd=ROOT,check=True)
    version=(ROOT/'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Invalid VERSION')
    files=release_files()
    output=ROOT/'dist'/f'codex-pet-accessories-{version}-source.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path,Path(f'codex-pet-accessories-{version}')/path.relative_to(ROOT))
    print(f'{output} ({len(files)} files)')


if __name__=='__main__':main()
