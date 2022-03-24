import ctypes
from .base import MemStruct, Field,field, init_mem_struct
from .remote import to_remote_type, RemoteMemStruct


def addressof(obj):
    return obj.remote.address if isinstance(obj, RemoteMemStruct) else ctypes.addressof(obj)
