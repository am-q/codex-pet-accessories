"""Required Windows verification before producing a release archive."""
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    commands=[['-B','-m','unittest','discover','-s','tests'],
              ['-B','scripts/verify_demo_privacy.py'],
              ['-B','scripts/verify_menu_scaling.py'],
              ['-B','scripts/verify_dpi_stability.py'],
              ['-B','scripts/verify_alpha_recovery.py'],
              ['-B','scripts/verify_lifecycle_windows.py'],
              ['-B','scripts/verify_window_stack.py']]
    for args in commands:
        subprocess.run([sys.executable,*args],cwd=ROOT,check=True,timeout=180)
    print('Windows verification passed: unit, native DPI, UI stress, alpha recovery, lifecycle, window stacking.')

if __name__=='__main__':main()
