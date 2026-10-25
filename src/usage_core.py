"""Read-only Codex quota client. Never starts a thread or inference turn."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
from query_process_guard import QueryProcessGuard

ALLOWED_METHODS = frozenset({'initialize', 'initialized', 'account/rateLimits/read'})


def codex_executable():
    found = shutil.which('codex')
    if found:
        return found
    root = Path(os.environ.get('LOCALAPPDATA', '')) / 'OpenAI/Codex/bin'
    choices = list(root.glob('*/codex.exe'))
    if not choices:
        raise RuntimeError('未找到 Codex，请先安装并登录 Codex。')
    return str(max(choices, key=lambda p: p.stat().st_mtime))


def normalize_quotas(payload):
    """Preserve every real window; missing values are never treated as zero."""
    buckets = payload.get('rateLimitsByLimitId')
    if not isinstance(buckets, dict) or not buckets:
        single = payload.get('rateLimits')
        buckets = {single.get('limitId') or 'codex': single} if isinstance(single, dict) else {}
    result = []
    for key, bucket in buckets.items():
        if not isinstance(bucket, dict):
            continue
        for slot in ('primary', 'secondary'):
            w = bucket.get(slot)
            if not isinstance(w, dict):
                continue
            used, duration, reset = w.get('usedPercent'), w.get('windowDurationMins'), w.get('resetsAt')
            finite = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            result.append({
                'bucket': str(key), 'name': bucket.get('limitName') or str(key), 'slot': slot,
                'used': max(0, min(100, used)) if finite(used) else None,
                'duration': duration if finite(duration) and duration > 0 else None,
                'reset': reset if finite(reset) and reset > 0 else None,
            })
    return result


def normalize_account_meta(payload):
    """Only retain public account/quota metadata, never account or credit IDs."""
    bucket=(payload.get('rateLimitsByLimitId') or {}).get('codex') or payload.get('rateLimits') or {}
    resets=payload.get('rateLimitResetCredits') or {}
    count=resets.get('availableCount')
    expiries=[c['expiresAt'] for c in resets.get('credits') or []
              if isinstance(c,dict) and c.get('status')=='available'
              and isinstance(c.get('expiresAt'),(int,float)) and c['expiresAt']>time.time()]
    return {'plan':bucket.get('planType'),'reset_count':count if isinstance(count,int) and not isinstance(count,bool) else None,
            'reset_credit_expires':min(expiries) if expiries else None}


def read_usage(timeout=30, cancel=None):
    """A short-lived official app-server; no credentials copied or logged."""
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    proc = subprocess.Popen(
        [codex_executable(), 'app-server', '--stdio'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding='utf-8', creationflags=flags,
    )
    guard = QueryProcessGuard(proc)
    inbox = queue.Queue()
    def receive():
        try:
            for line in proc.stdout:
                try:
                    inbox.put(json.loads(line))
                except ValueError:
                    pass
        finally:
            inbox.put(None)
    reader = threading.Thread(target=receive, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    def send(method, ident=None, params=None):
        if method not in ALLOWED_METHODS:
            raise ValueError('Unsupported method')
        msg = {'method': method}
        if ident is not None:
            msg['id'] = ident
        if params is not None:
            msg['params'] = params
        proc.stdin.write(json.dumps(msg) + '\n')
        proc.stdin.flush()
    def wait(ident):
        while True:
            if cancel is not None and cancel.is_set():
                raise RuntimeError('查询已取消')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('额度查询超时')
            try:
                msg = inbox.get(timeout=min(remaining, .5))
            except queue.Empty:
                continue
            if msg is None:
                raise RuntimeError('Codex 查询进程提前退出')
            if msg.get('id') == ident:
                if 'error' in msg:
                    # Never persist raw server output (which could contain account data).
                    err = str(msg['error'].get('message', '')).lower()
                    if 'auth' in err or 'login' in err:
                        raise RuntimeError('登录状态不可用，请在 Codex 中确认登录后刷新')
                    raise RuntimeError('额度接口暂时不可用，请稍后刷新')
                return msg.get('result', {})
    try:
        send('initialize', 1, {'clientInfo': {'name': 'pet_usage_base', 'title': 'Pet Usage Base', 'version': '0.1.0'}})
        wait(1)
        send('initialized', params={})
        send('account/rateLimits/read', 2)
        payload=wait(2)
        return {'checked_at': time.time(), 'quotas': normalize_quotas(payload),'account':normalize_account_meta(payload)}
    finally:
        guard.close()  # Also kills any descendants if the accessory is terminated.
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        reader.join(timeout=1)
        for pipe in (proc.stdin, proc.stdout):
            if pipe:
                pipe.close()


def period_label(minutes):
    if minutes is None:
        return '额度'
    if minutes == 10080:
        return '周额度'
    if minutes % 1440 == 0:
        return f'{minutes / 1440:g} 天额度'
    if minutes % 60 == 0:
        return f'{minutes / 60:g} 小时额度'
    return f'{minutes:g} 分钟额度'


def countdown(reset, now=None):
    if reset is None:
        return '重置时间未知'
    seconds = reset - (time.time() if now is None else now)
    if seconds <= 0:
        return '已到重置时间 · 待确认'
    minutes = math.ceil(seconds / 60)
    days, remainder = divmod(minutes, 1440)
    hours, mins = divmod(remainder, 60)
    if days:
        return f'{days} 天 {hours} 小时后重置'
    if hours:
        return f'{hours} 小时 {mins} 分钟后重置'
    return f'{mins} 分钟后重置'


def next_delay(base, failures=0):
    return min(1800, base * (2 ** min(failures, 6)))


def choose_position(anchor, size, width, height, offset=(0, 0)):
    """Codex saves mascot top-left in device-independent coordinates."""
    screen = anchor.get('displayBounds') or {'x': 0, 'y': 0, 'width': 1920, 'height': 1080}
    left, top = screen['x'] + 8, screen['y'] + 8
    right, bottom = screen['x'] + screen['width'] - 8, screen['y'] + screen['height'] - 8
    ax, ay = anchor['x'], anchor['y']
    x = ax + size / 2 - width / 2
    # Leave room for the official pet's hover controls.
    y = ay + math.ceil(size * 208 / 192) + 42
    placement = 'below'
    # Keep the plinth horizontally attached. Never jump to the side when
    # close to a screen edge; tighten the vertical gap first.
    if y + height > bottom:
        y = bottom-height
        if y < ay + math.ceil(size * 208 / 192):
            y = ay-height-6
            placement = 'above'
    x += offset[0]
    y += offset[1]
    return round(max(left, min(x, right - width))), round(max(top, min(y, bottom - height))), placement


class PetState:
    """Only reads the pet's saved layout; never edits Codex configuration."""
    def __init__(self, home=None):
        self.path = Path(home or os.environ.get('CODEX_HOME') or Path.home() / '.codex') / '.codex-global-state.json'
        self.stamp = None
        self.state = None
        self.next_read = 0

    def read(self):
        if time.monotonic()<self.next_read:
            return self.state
        self.next_read=time.monotonic()+.35
        try:
            stamp = self.path.stat().st_mtime_ns
            if stamp != self.stamp:
                raw = json.loads(self.path.read_text(encoding='utf-8'))
                b = raw.get('electron-avatar-overlay-bounds')
                atoms = raw.get('electron-persisted-atom-state') or {}
                if isinstance(b, dict) and all(isinstance(b.get(k), (int, float)) for k in ('x', 'y')):
                    self.state = {
                        'open': raw.get('electron-avatar-overlay-open') is True,
                        'anchor': {k: b[k] for k in ('x', 'y', 'displayBounds') if k in b},
                        'size': atoms.get('avatar-overlay-mascot-width-px', 112),
                    }
                self.stamp = stamp
        except (OSError, ValueError, TypeError):
            pass  # An in-progress atomic write is retried on the next tick.
        return self.state
