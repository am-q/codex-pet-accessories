"""Run the shipped EXE with Python removed from PATH and isolated demo data."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def verify(archive_path):
    archive_path = Path(archive_path).resolve()
    with tempfile.TemporaryDirectory(prefix='Codex Portable 测试 ') as folder:
        root = Path(folder)
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip():
                raise RuntimeError('Portable ZIP integrity check failed')
            for entry in archive.infolist():
                target = (root / entry.filename).resolve()
                target.relative_to(root.resolve())
            archive.extractall(root)
        executables = list(root.rglob('CodexPetAccessories.exe'))
        if len(executables) != 1:
            raise RuntimeError('Portable archive must contain one application executable')
        executable = executables[0]
        if executable.read_bytes()[:2] != b'MZ':
            raise RuntimeError('Application is not a Windows executable')
        data = root / 'isolated-demo-data'
        report = root / 'smoke-result.json'
        environment = os.environ.copy()
        for name in ('PYTHONPATH', 'PYTHONHOME', 'TCL_LIBRARY', 'TK_LIBRARY'):
            environment.pop(name, None)
        windows = Path(environment.get('WINDIR', r'C:\Windows'))
        environment['PATH'] = os.pathsep.join((str(windows / 'System32'), str(windows)))
        environment['CODEX_PET_DATA_DIR'] = str(data)
        result = subprocess.run([str(executable), '--smoke', '--data-dir', str(data),
                                 '--report', str(report)], cwd=root, env=environment,
                                capture_output=True, timeout=90,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode or not report.is_file():
            error = (data / 'error.log').read_text(encoding='utf-8') if (data / 'error.log').exists() else ''
            raise RuntimeError(f'Portable application failed: exit={result.returncode}; {error[-3000:]}')
        evidence = json.loads(report.read_text(encoding='utf-8'))
        assert evidence['ui'] == 'ok' and evidence['standalone'] is True, evidence
        assert evidence['scheduler_resource'] is True and len(evidence['styles']) == 7, evidence
        assert evidence['auto_start_uses_executable'] is True, evidence
        assert not list(data.glob('*.json')), 'Demo mode persisted runtime data'
        result = {'portable': 'passed', 'python_on_path': False,
                  'unicode_and_spaces_path': True, 'version': evidence['version'],
                  'styles': len(evidence['styles']), 'scheduler_resource': True,
                  'personal_data_written': False,
                  'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest()}
        print(json.dumps(result, ensure_ascii=False))
        return result


if __name__ == '__main__':
    verify(sys.argv[1])
