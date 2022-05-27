import ctypes
from .base import MemStruct, Field, field, init_mem_struct, VTableFunc, ClassFunc, bit_mask, CFunc, Enum, Enumerate, init_enum
from .remote import to_remote_type, RemoteMemStruct


def addressof(obj):
    return obj.remote.address if isinstance(obj, RemoteMemStruct) else ctypes.addressof(obj)
