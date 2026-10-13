"""Linux birth time via statx, with an honest unknown fallback."""
import ctypes, os, struct
try:
    _statx=ctypes.CDLL(None,use_errno=True).statx
    _statx.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_uint,ctypes.c_void_p]
    _statx.restype=ctypes.c_int
except AttributeError:_statx=None

def birth_time(path):
    if _statx is None:return None
    buf=ctypes.create_string_buffer(256)
    if _statx(-100,os.fsencode(path),0x100,0x800,buf)!=0:return None
    if not struct.unpack_from('=I',buf.raw)[0]&0x800:return None
    seconds,nanos=struct.unpack_from('=qI',buf.raw,80)
    return seconds+nanos/1e9
