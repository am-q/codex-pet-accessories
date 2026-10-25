import contextlib
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import runtime_support as runtime
import pet_lifecycle


class PortableRuntimeTests(unittest.TestCase):
    def test_source_version_comes_from_project(self):
        self.assertEqual(runtime.application_version(),
                         (Path(__file__).resolve().parents[1] / 'VERSION').read_text().strip())

    def test_frozen_resources_and_launcher_do_not_point_at_python(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder) / 'bundle'
            bundle.mkdir()
            (bundle / 'VERSION').write_text('7.8.9', encoding='utf-8')
            executable = str(Path(folder) / 'Portable App.exe')
            with mock.patch.object(sys, 'frozen', True, create=True), \
                 mock.patch.object(sys, '_MEIPASS', str(bundle), create=True), \
                 mock.patch.object(sys, 'executable', executable):
                self.assertEqual(runtime.application_version(), '7.8.9')
                self.assertEqual(runtime.resource_path('pet_lifecycle_task.ps1'), bundle / 'pet_lifecycle_task.ps1')
                self.assertEqual(runtime.startup_launcher('unused.py'), (Path(executable), None))

    def test_frozen_task_uses_persistent_executable_and_standalone_mode(self):
        with tempfile.TemporaryDirectory() as folder, \
             mock.patch.object(sys, 'frozen', True, create=True), \
             mock.patch.object(sys, '_MEIPASS', folder, create=True), \
             mock.patch.object(sys, 'executable', str(Path(folder) / 'Portable App.exe')), \
             mock.patch.object(pet_lifecycle, 'external_process_environment', return_value=contextlib.nullcontext({})), \
             mock.patch.object(pet_lifecycle, 'log_event'), \
             mock.patch.object(pet_lifecycle.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            pet_lifecycle.configure_auto_start(Path(folder) / 'data', 'temporary-source.py', True)
            command = run.call_args.args[0]
            self.assertIn('-Standalone', command)
            self.assertNotIn('-Script', command)
            self.assertEqual(command[command.index('-Python') + 1], sys.executable)

    def test_external_dll_path_is_restored_after_spawn_failure(self):
        kernel = mock.MagicMock()
        def previous(length, buffer):
            buffer.value = r'C:\bundle'
            return len(buffer.value)
        kernel.GetDllDirectoryW.side_effect = previous
        kernel.SetDllDirectoryW.return_value = True
        with mock.patch.object(sys, 'frozen', True, create=True), \
             mock.patch.object(sys, '_MEIPASS', r'C:\bundle', create=True), \
             mock.patch.object(runtime.ctypes, 'WinDLL', return_value=kernel), \
             mock.patch.dict(runtime.os.environ, {'PATH': r'C:\bundle;C:\bundle\bin;C:\Windows\System32'}):
            with self.assertRaisesRegex(RuntimeError, 'test spawn failure'):
                with runtime.external_process_environment() as environment:
                    self.assertEqual(environment['PATH'], r'C:\Windows\System32')
                    raise RuntimeError('test spawn failure')
        self.assertEqual(kernel.SetDllDirectoryW.call_args_list,
                         [mock.call(None), mock.call(r'C:\bundle')])

    def test_windowed_diagnostic_result_does_not_require_stdout(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(sys, 'stdout', None):
            path = Path(folder) / 'report.json'
            runtime.emit_report({'ui': 'ok'}, path)
            self.assertIn('"ui": "ok"', path.read_text(encoding='utf-8'))
            runtime.emit_report({'ui': 'ok'})


if __name__ == '__main__':
    unittest.main()
