import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('package_release',ROOT/'scripts/package_release.py')
release=importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_manifest_excludes_local_data(self):
        files=[p.relative_to(ROOT).as_posix() for p in release.release_files()]
        self.assertIn('LICENSE',files)
        self.assertIn('src/accessories.py',files)
        self.assertIn('docs/styles.png',files)
        blocked={'.venv','data','backups','vendor','__pycache__','dist','.git'}
        for name in files:
            self.assertFalse(set(Path(name).parts)&blocked,name)
            self.assertNotIn(Path(name).name,('auth.json','settings.json','usage.json','startup.json'))

    def test_example_contains_no_account_or_renewal_data(self):
        sample=json.loads((ROOT/'examples/settings.example.json').read_text(encoding='utf-8'))
        self.assertEqual(sample['interval'],300)
        self.assertNotIn('renewal_date',sample)
        self.assertNotIn('position',sample)
        self.assertNotIn('account',sample)


if __name__=='__main__':unittest.main()
