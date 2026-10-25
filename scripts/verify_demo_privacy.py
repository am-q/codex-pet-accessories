"""Exercise demo windows with every private-data entry point forbidden."""
import json
from pathlib import Path
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import pet_base
from dpi_policy import initialize_native_dpi
from smooth_surface import sharp_window

initialize_native_dpi()
with tempfile.TemporaryDirectory() as folder, \
     mock.patch.object(pet_base, 'DATA', Path(folder)), \
     mock.patch.object(pet_base, 'load_json', side_effect=AssertionError('Demo read local settings')), \
     mock.patch.object(pet_base.PetState, 'read', side_effect=AssertionError('Demo read native pet state')), \
     mock.patch.object(pet_base, 'read_usage', side_effect=AssertionError('Demo queried an account')), \
     mock.patch.object(pet_base.LivePetTracker, 'update', side_effect=AssertionError('Demo tracked a real window')):
    root = sharp_window()
    app = pet_base.App(root, demo=True)
    try:
        root.update()
        app.show_details()
        app.popup.change_page('appearance')
        app.set_appearance('accessory_style', 'feather')
        root.update()
        app.collapse()
        assert not list(Path(folder).iterdir()), 'Demo wrote personal-style runtime data'
    finally:
        app.close()
print(json.dumps({'demo_privacy': 'passed', 'private_settings_reads': 0,
                  'pet_state_reads': 0, 'account_queries': 0, 'runtime_files_written': 0}))
