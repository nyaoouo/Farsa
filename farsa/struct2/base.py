import ctypes
import enum

import _ctypes
from typing import TypeVar, Type

_t = TypeVar('_t')


def set_cdata_type_size(type_, new_size):
    # black magic only tested in python 3.10 win 64 bit
    ctypes.c_int64.from_address(ctypes.c_int64.from_address(id(type_) + 0x108).value + 0x30).value = new_size


def get_data(_data, max_lv=10, lv=0):
    if lv >= max_lv:
        return _data.__repr__()
    if isinstance(_data, enum.Enum):
        return _data.name
    elif isinstance(_data, MemStruct):
        return _data._get_data(max_lv, lv + 1) or {
            f.name: get_data(getattr(_data, f.name), max_lv, lv + 1)
            for f in _data._m_fields_.values()
        }
    elif isinstance(_data, _ctypes.Array):
        return [get_data(d, max_lv, lv + 1) for d in _data]
    return _data


class MemMeta(type(ctypes.Structure)):
    @classmethod
    def __prepare__(metacls, name, bases, **kwargs):
        res = super().__prepare__(name, bases, **kwargs)
        res['_m_fields_'] = {}
        return res

    def __new__(cls, name, bases, namespace, **kwargs):
        fields = {}
        for b in bases:
            if field := getattr(b, '_m_fields_', None):
                fields |= field
        namespace['_m_fields_'] = fields | namespace.get('_m_fields_', {})
        res = super().__new__(cls, name, bases, namespace, **kwargs)
        if size := getattr(res, '_size_', 0):
            set_cdata_type_size(res, size)
        return res


class MemStruct(ctypes.Structure, metaclass=MemMeta):
    _size_ = 0
    _fields_ = []
    _m_fields_ = {}

    def __iter__(self):
        for key in self._m_fields_.keys():
            yield key,getattr(self,key)


    def __copy__(self):
        return self.__class__.from_buffer_copy(self)

    def __init__(self, **kw):
        super().__init__()
        for k, v in kw.items(): setattr(self, k, v)

    def __rshift__(self, other: Type[_t]) -> _t:
        return other.from_address(ctypes.addressof(self))

    def __init_subclass__(cls, auto=True):
        if auto:
            size = max(getattr(b, '_size_', 0) for b in cls.__bases__ if issubclass(b, MemStruct))
            for attr in cls._m_fields_.values():
                if attr.offset is None: attr.offset = size
                _size = 4 if issubclass((d_type := attr.d_type), enum.Enum) else ctypes.sizeof(d_type)
                size = max(size, attr.offset + _size)
            setattr(cls, '_size_', max(size, cls._size_))
        super().__init_subclass__()

    def get_data(self, max_lv=4, lv=0):
        return get_data(self, max_lv, lv)

    def _get_data(self, max_lv=10, lv=0):
        pass

    def __str__(self):
        return str(self.get_data())

    @classmethod
    def offset(cls: Type[_t], offset: int) -> Type[_t]:
        return type(cls.__name__, (cls,), {
            k: (v + offset) for k, v in cls._m_fields_.items()
        })
