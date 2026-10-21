"""Specific Windows proof of the real windowed private route; never opens USB."""
import ctypes
from ctypes import wintypes
from importlib import util
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time

from mars_display import usb_ipc as ipc
from mars_display.usb_process import OwnedWorker, WindowsGate


def require_host():
    if os.name != 'nt':
        raise RuntimeError('Native Windows worker qualification required')


def _environment(root):
    spec = util.spec_from_file_location('p3_smoke_environment', Path(__file__).with_name('smoke.py'))
    module = util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.environment(root)


def _launch(executable, env, port, nonce):
    return subprocess.Popen([str(executable), '--usb-worker', str(port), nonce],
        cwd=executable.parent, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)


def _listener():
    channel = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    channel.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    channel.bind(('127.0.0.1', 0)); channel.listen(1); channel.settimeout(5)
    return channel


def exchange(executable, env, malformed=False):
    nonce=secrets.token_hex(32)
    with _listener() as listener:
        owner=OwnedWorker(listener.getsockname()[1],nonce,ipc.Budgets(),
            launcher=lambda port,token:_launch(executable,env,port,token))
        try:
            owner.start();owner.wait_start(time.monotonic()+5,threading.Event())
            with listener.accept()[0] as channel:
                if ipc.receive_packet(channel,time.monotonic()+5)!=(ipc.HELLO,0,bytes.fromhex(nonce)):
                    raise RuntimeError('Packaged worker handshake mismatch')
                if malformed:
                    channel.settimeout(2)
                    channel.sendall(ipc.HEADER.pack(b'MUSB',1,ipc.FRAME,0,1,0xffffffff))
                    if channel.recv(1)!=b'':
                        raise RuntimeError('Packaged worker accepted malformed IPC')
                    if owner.child.wait(timeout=2)!=1:
                        raise RuntimeError('Packaged worker malformed exit mismatch')
                else:
                    ipc.send_packet(channel,ipc.CLOSE,1,b'',time.monotonic()+2)
                    if ipc.receive_packet(channel,time.monotonic()+2)!=(ipc.REPLY,1,b'\x00'):
                        raise RuntimeError('Packaged worker close reply mismatch')
                    if owner.child.wait(timeout=2)!=0:
                        raise RuntimeError('Packaged worker close exit mismatch')
        finally:
            owner.stop(time.monotonic()+2)
        if not owner.closed:
            raise RuntimeError('Packaged worker ownership not released')


def held_gate(executable, env):
    nonce=secrets.token_hex(32);gate=WindowsGate(nonce);child=None
    gate.open()
    try:
        with _listener() as listener:
            child=_launch(executable,env,listener.getsockname()[1],nonce)
            gate.assign(child);listener.settimeout(0.3)
            try: listener.accept()
            except socket.timeout: pass
            else: raise RuntimeError('Packaged worker connected before admission')
            if child.poll() is not None:
                raise RuntimeError('Packaged worker did not await admission')
            gate.close();child.wait(timeout=2);gate.close_process(child)
    finally:
        if child is not None:
            if child.poll() is None:child.kill()
            child.wait(timeout=2);gate.close_process(child)
        gate.close()


def parent_death(executable, env, scratch):
    """Kill a test parent we created; observe its child by exact process handle."""
    fixture=Path(__file__).resolve().parents[1]/'tests/usb_native_fixture.py'
    report=scratch/'child.pid'
    parent_env=dict(env)
    parent_env['PYTHONPATH']=str(fixture.parents[1]/'src')
    parent=subprocess.Popen([sys.executable,'-B',str(fixture),'parent',str(executable),str(report)],
        env=parent_env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    api.OpenProcess.restype=wintypes.HANDLE
    api.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    api.WaitForSingleObject.restype=wintypes.DWORD
    api.CloseHandle.argtypes=[wintypes.HANDLE];api.CloseHandle.restype=wintypes.BOOL
    handle=None
    try:
        deadline=time.monotonic()+10
        while not report.exists():
            if parent.poll() is not None or time.monotonic()>=deadline:
                raise RuntimeError('Packaged parent-death fixture failed admission')
            threading.Event().wait(0.01)
        text=report.read_text()
        if not text.isdigit():raise RuntimeError('Invalid owned child observation')
        handle=api.OpenProcess(0x100000,False,int(text))
        if not handle or api.WaitForSingleObject(handle,0)!=0x102:
            raise RuntimeError('Cannot observe live owned packaged child')
        parent.kill();parent.wait(timeout=2)
        if api.WaitForSingleObject(handle,2000)!=0:
            raise RuntimeError('Owned packaged child survived parent death')
    finally:
        if parent.poll() is None:parent.kill()
        parent.wait(timeout=2)
        if handle and not api.CloseHandle(handle):
            raise RuntimeError('Owned observer handle cleanup failed')


def check(folder, scratch):
    require_host()
    folder,scratch=Path(folder).absolute(),Path(scratch).absolute()
    executable=folder/'MarsDisplay.exe'
    if not executable.is_file() or executable.is_symlink():
        raise ValueError('Missing exact packaged worker executable')
    env=_environment(scratch)
    for args in (['--usb-worker'],['--usb-worker=invalid'],['--usb-worker','0','a'*64]):
        result=subprocess.run([str(executable),*args],env=env,cwd=folder,
            stdin=subprocess.DEVNULL,capture_output=True,timeout=5)
        if (result.returncode,result.stdout,result.stderr)!=(2,b'',b''):
            raise RuntimeError('Packaged private rejection streams/exit mismatch')
    exchange(executable,env)
    exchange(executable,env,malformed=True)
    held_gate(executable,env)
    parent_death(executable,env,scratch)
    # An accidental ordinary-app launch would touch its settings/lock directory.
    if any((scratch/name/'MarsDisplay').exists() for name in ('local','roaming')):
        raise RuntimeError('Packaged worker entered application settings startup')
    return {'status':'passed','scope':'real windowed EXE; no OPEN or device request',
            'private_rejections':3,'hello_close':'passed','malformed_ipc':'passed',
            'held_startup_gate':'passed','parent_death':'passed','owned_reap':'passed',
            'app_settings_startup':'absent'}
