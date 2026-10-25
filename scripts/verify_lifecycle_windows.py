import ctypes,json,subprocess,sys,tempfile,time
from pathlib import Path
from ctypes import wintypes as W
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from query_process_guard import QueryProcessGuard

# A disposable query-like process spawns a descendant only after joining the job.
child_code="import subprocess,sys,time;sys.stdin.readline();p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],creationflags=0x08000000);print(p.pid,flush=True);time.sleep(60)"
proc=subprocess.Popen([sys.executable,'-c',child_code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,creationflags=0x08000000)
guard=QueryProcessGuard(proc)
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];k.WaitForSingleObject.restype=W.DWORD
k.CloseHandle.argtypes=[W.HANDLE]
handles=[]
try:
    proc.stdin.write('start\n');proc.stdin.flush()
    descendant=int(proc.stdout.readline().strip())
    for pid in (proc.pid,descendant):
        handle=k.OpenProcess(0x100000,False,pid);assert handle;handles.append(handle)
    guard.close()
    for h in handles:assert k.WaitForSingleObject(h,5000)==0,'Query descendant survived'
    proc.wait(timeout=5)
finally:
    guard.close()
    for h in handles:k.CloseHandle(h)
    if proc.poll() is None:proc.kill();proc.wait(timeout=5)
    proc.stdin.close();proc.stdout.close()
print('query_child_and_descendant_cleanup: ok')

# Exercise real App shutdown with simulated host/pet state, never the native UI.
from dpi_policy import initialize_native_dpi
initialize_native_dpi()
import pet_base
from smooth_surface import sharp_window
from types import SimpleNamespace
original_data=pet_base.DATA
with tempfile.TemporaryDirectory() as folder:
    pet_base.DATA=Path(folder)
    try:
        for reason in ('codex_exit','pet_closed'):
            root=sharp_window();app=pet_base.App(root,demo=True)
            app.demo=False;app.last_alive_check=time.monotonic()
            app.codex_alive=reason!='codex_exit'
            app.settings['auto_start']=True
            app.pet=SimpleNamespace(read=lambda:{'open':False})
            app.pet_closed_since=time.monotonic()-3
            app.tick_once()
            assert app.closed
            result=json.loads((Path(folder)/'runtime.json').read_text('utf-8'))
            assert result['state']=='closed' and result['reason']==reason
        root=sharp_window();app=pet_base.App(root,demo=True)
        app.show_details();menu=app.popup
        initial=app.settings.get('auto_start',False)
        menu.toggle_auto_start();assert app.settings['auto_start'] is not initial
        menu.toggle_auto_start();assert app.settings['auto_start'] is initial
        app.close('test_complete')
    finally:pet_base.DATA=original_data
print('codex_exit_and_pet_close_and_menu_toggle: ok; personal_settings_unchanged: true')
