import ctypes
from typing import TypeVar, Type, TYPE_CHECKING

from .field import Field

_t = TypeVar('_t')


class MemStruct(ctypes.Structure):
    _size_: int = 0
    _fields_ = []

    if TYPE_CHECKING:
        def __iter__(self):
            pass

    def __copy__(self):
        return self.__class__.from_buffer_copy(self)

    def __init__(self, **kw):
        super().__init__()
        for k, v in kw.items(): setattr(self, k, v)

    def __rshift__(self, other: Type[_t]) -> _t:
        return other.from_address(ctypes.addressof(self))


class AutoMemStruct(MemStruct):
    def __init_subclass__(cls):
        size = 0
        for name, attr in cls.__dict__.items():
            if isinstance(attr, Field):
                if attr.offset is None: attr.offset = size
                size = max(size, attr.offset + ctypes.sizeof(attr.d_type))
        setattr(cls, '_size_', size)
        super().__init_subclass__()


def set_cdata_type_size(type_, new_size):
    # black magic only tested in python 3.10 win 64 bit
    ctypes.c_int64.from_address(ctypes.c_int64.from_address(id(type_) + 0x108).value + 0x30).value = new_size


def init_mem_struct(cls: Type[_t]) -> Type[_t]:
    set_cdata_type_size(cls, cls._size_)
    return cls
    # return type(cls.__name__, (ctypes.c_char * cls._size_, cls), {})
