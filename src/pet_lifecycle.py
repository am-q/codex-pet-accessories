"""Accessory-only scheduling and diagnostics; never changes Codex configuration."""
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from runtime_support import resource_path, startup_launcher, external_process_environment

_crash_stream=None

def log_event(data,event,**fields):
    try:
        data=Path(data);data.mkdir(parents=True,exist_ok=True)
        path=data/'lifecycle.log'
        if path.exists() and path.stat().st_size>1024*1024:
            path.replace(data/'lifecycle.previous.log')
        record=dict(time=time.strftime('%Y-%m-%d %H:%M:%S'),pid=os.getpid(),event=event,**fields)
        with path.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
    except OSError:pass

def status(data,state,**fields):
    try:
        data=Path(data);data.mkdir(parents=True,exist_ok=True)
        path=data/'runtime.json';temp=data/'runtime.tmp'
        temp.write_text(json.dumps(dict(time=time.time(),pid=os.getpid(),state=state,**fields),ensure_ascii=False),encoding='utf-8')
        temp.replace(path)
    except OSError:pass

def log_exception(data,kind,exc_info):
    log_event(data,kind,error_type=exc_info[0].__name__)
    try:
        p=Path(data)/'error.log'
        if p.exists() and p.stat().st_size>1024*1024:p.replace(p.with_name('error.previous.log'))
        with p.open('a',encoding='utf-8') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S')+' '+kind+'\n'+''.join(traceback.format_exception(*exc_info)))
    except OSError:pass

def enable_crash_log(data):
    global _crash_stream
    try:
        Path(data).mkdir(parents=True,exist_ok=True)
        _crash_stream=(Path(data)/'native-crash.log').open('a',encoding='utf-8')
        faulthandler.enable(file=_crash_stream,all_threads=True)
    except (OSError,RuntimeError):pass

def should_auto_start(settings,desktop_alive,pet):
    return settings.get('auto_start') is True and desktop_alive and bool(pet and pet.get('open') is True)

def exit_reason(desktop_alive,pet,auto_start):
    if not desktop_alive:return 'codex_exit'
    if auto_start and pet is not None and pet.get('open') is False:return 'pet_closed'
    return None

def task_name(data):
    key=str(Path(data).resolve()).casefold().encode('utf-8')
    return 'CodexPetAccessories-'+hashlib.sha256(key).hexdigest()[:12]

def configure_auto_start(data,script,enabled):
    helper=resource_path('pet_lifecycle_task.ps1')
    executable,source_script=startup_launcher(script)
    command=['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden',
        '-ExecutionPolicy','Bypass','-File',str(helper),'-Mode','enable' if enabled else 'disable',
        '-TaskName',task_name(data),'-Python',str(executable),
        '-DataDir',str(Path(data).resolve())]
    if source_script is None:command+=['-Standalone']
    else:command+=['-Script',str(source_script)]
    with external_process_environment() as environment:
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',
            timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),env=environment)
    if result.returncode:
        log_event(data,'auto_start_config_failed',enabled=enabled)
        raise RuntimeError('自动启停设置未成功保存，请查看 Windows 计划任务权限。')
    log_event(data,'auto_start_configured',enabled=enabled,task=task_name(data))

