import functools
import ctypes, _ctypes
import copy
from typing import TypeVar, Type, Generic, Any
from .utils import import_type, get_str_size
from .enum import Enum

_t = TypeVar('_t')


@functools.cache
def parse_type(type_):
    if isinstance(type_, str): return parse_type(import_type(type_))
    if issubclass(type_, Enum): return type_, default_get, enum_set
    if issubclass(type_, _ctypes._SimpleCData): return type_, simple_c_get, simple_c_set
    if issubclass(type_, _ctypes.Array):
        if type_._type_ == ctypes.c_char or type_._type_ == ctypes.c_wchar: return type_, simple_c_get, simple_c_set
        return type_, default_get, array_set
    return type_, default_get, default_set


def default_get(type_, address): return type_.from_address(address)


def default_set(type_, address, val): ctypes.cast(address, ctypes.POINTER(type_))[0] = val


def enum_set(type_, address, val):  type_._base_.from_address(address).value = val.value if isinstance(val, Enum) else val


def simple_c_get(type_, address): return type_.from_address(address).value


def simple_c_set(type_, address, val): type_.from_address(address).value = val


def array_set(type_, address, val): type_.from_address(address)[:len(val)] = val


class FieldBase(Generic[_t]):
    offset: int
    name: str

    def __get__(self, instance, owner) -> _t: ...

    def __set__(self, instance, owner) -> _t: ...

    def __add__(self, offset: int):
        new_f = copy.deepcopy(self)
        new_f.offset += offset
        return new_f

    def __set_name__(self, owner, name):
        owner._m_fields_[name] = self
        self.name = name


class Field(FieldBase[_t]):
    _real_d_type = None
    _getter = None
    _setter = None

    def __init__(self, d_type: Type[_t] | str, offset: int | None = None, auto_pad: int = None):
        self._d_type = d_type
        self.offset = offset
        self.auto_pad = auto_pad

    def init_type(self):
        self._real_d_type, self._getter, self._setter = res = parse_type(self._d_type)
        return res

    d_type = property(lambda self: self.init_type()[0] if self._real_d_type is None else self._real_d_type)
    getter = property(lambda self: self.init_type()[1] if self._getter is None else self._getter)
    setter = property(lambda self: self.init_type()[2] if self._setter is None else self._setter)
    i_size = property(lambda self: get_str_size(self._d_type) if isinstance(self._d_type, (str, bytes)) else ctypes.sizeof(self.d_type))

    def __get__(self, instance, owner) -> _t:
        if instance is None: return self
        return self.getter(self.d_type, ctypes.addressof(instance) + self.offset)

    def __set__(self, instance, value: _t) -> None:
        if instance is None: return
        return self.setter(self.d_type, ctypes.addressof(instance) + self.offset, value)


def field(tp: Type[_t] | Any, offset=None, auto_pad: int = None) -> _t:
    return Field(tp, offset, auto_pad)


class BitField(FieldBase[int]):
    def __init__(self, offset=None, bit_offset=None, bit_size=1):
        self.offset = offset
        self.bit_offset = bit_offset
        self.bit_size = bit_size
        self.mask = (1 << bit_size) - 1

    def __get__(self, instance, owner):
        if instance is None: return self
        return (ctypes.c_ubyte.from_address(
            ctypes.addressof(instance) + self.offset
        ).value >> self.bit_offset) & self.mask

    def __set__(self, instance, value):
        if instance is None: return self
        v = ctypes.c_ubyte.from_address(ctypes.addressof(instance) + self.offset)
        v.value = (v.value & ~(self.mask << self.bit_offset)) | (value << self.bit_offset)


bit_field = BitField
