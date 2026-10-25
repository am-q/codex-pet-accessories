"""Keep the accessory's quota subprocess tree inside a kill-on-close job."""
import ctypes
from ctypes import wintypes as W
import os

class QueryProcessGuard:
    def __init__(self,proc):
        self.handle=None
        if os.name!='nt':return
        class BASIC(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',W.DWORD),
                      ('min_working_set',ctypes.c_size_t),('max_working_set',ctypes.c_size_t),
                      ('active_processes',W.DWORD),('affinity',ctypes.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
        class IO(ctypes.Structure):
            _fields_=[(name,ctypes.c_uint64) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class EXTENDED(ctypes.Structure):
            _fields_=[('basic',BASIC),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
                      ('peak_process_memory',ctypes.c_size_t),('peak_job_memory',ctypes.c_size_t)]
        k=ctypes.WinDLL('kernel32',use_last_error=True);self.k=k
        k.CreateJobObjectW.argtypes=[ctypes.c_void_p,W.LPCWSTR];k.CreateJobObjectW.restype=W.HANDLE
        k.SetInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD];k.SetInformationJobObject.restype=W.BOOL
        k.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE];k.AssignProcessToJobObject.restype=W.BOOL
        k.CloseHandle.argtypes=[W.HANDLE]
        self.handle=k.CreateJobObjectW(None,None)
        try:
            if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
            limits=EXTENDED();limits.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not k.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not k.AssignProcessToJobObject(self.handle,W.HANDLE(int(proc._handle))):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            proc.kill();proc.wait(timeout=5);self.close();raise

    def close(self):
        if self.handle:
            self.k.CloseHandle(self.handle);self.handle=None

