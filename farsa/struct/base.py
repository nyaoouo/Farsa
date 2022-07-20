import re
import ctypes
import copy
import inspect
from importlib import import_module
from typing import TypeVar, Type, TYPE_CHECKING

import _ctypes

_t = TypeVar('_t')


def import_type(type_str):
    if type_str.endswith(' *'): return ctypes.POINTER(import_type(type_str[:-2]))
    is_array = re.search(r' \[(\d+)]$', type_str)
    if is_array: return import_type(type_str[:is_array.start()]) * int(is_array.group(1))
    module_name, attr_name = type_str.split(':')
    d_type = import_module(module_name)
    # for k in attr_name.split('.'): d_type = getattr(d_type, k)
    d_type = eval(attr_name, globals() | d_type.__dict__)
    assert inspect.isclass(d_type), TypeError(f'{d_type} is not a class')
    return d_type


def get_data(_data, max_lv=10, lv=0):
    if lv >= max_lv: return _data.__repr__()
    if isinstance(_data, MemStruct):
        return _data._get_data(max_lv, lv + 1) or {
            k: get_data(getattr(_data, k), max_lv, lv + 1)
            for k in _data._p_field
        }
    elif isinstance(_data, _ctypes.Array):
        return [get_data(d, max_lv, lv + 1) for d in _data]
    return _data


class MemStruct(ctypes.Structure):
    _pack_ = 1
    _size_ = None
    _p_field = []

    if TYPE_CHECKING:
        def __iter__(self):
            pass

    def __copy__(self):
        return self.__class__.from_buffer_copy(self)

    def __init__(self, **kw):
        super().__init__()
        for k, v in kw.items(): setattr(self, k, v)

    def get_data(self, max_lv=4, lv=0):
        return get_data(self, max_lv, lv)

    def _get_data(self, max_lv=10, lv=0):
        pass

    def __rshift__(self, other: Type[_t]) -> _t:
        return other.from_address(ctypes.addressof(self))

    def __str__(self):
        return str(self.get_data())

    @classmethod
    def offset(cls: _t, offset) -> _t:
        attr = {}
        for k in dir(cls):
            v = getattr(cls, k)
            if isinstance(v, Field):
                attr[k] = v + offset
            elif isinstance(v, VTableFunc):
                pass
        attr['_size_'] = cls._size_ + offset
        attr['_fields_'] = [('', ctypes.c_byte * offset)]
        return type(f'{cls.__name__}(+{offset})', (cls,), attr)


class Fid:
    counter = 0

    @classmethod
    def get(cls):
        cls.counter += 1
        return cls.counter


class Field:
    def __init__(self, d_type: Type[_t] | str, offset: int | None = None):
        self._d_type = d_type
        self._real_d_type = None
        self._mode = 0
        self.offset = offset
        self._fid = Fid.get()

    @property
    def d_type(self):
        if self._real_d_type is None:
            self._real_d_type = import_type(self._d_type) if isinstance(self._d_type, str) else self._d_type
            if issubclass(self._real_d_type, Enum):
                self._mode = 1
            elif issubclass(self._real_d_type, _ctypes.Array):
                if self._real_d_type._type_ == ctypes.c_char or self._real_d_type._type_ == ctypes.c_wchar:
                    self._mode = 2  # is bytes
                # elif ctypes.sizeof(self._real_d_type._type_) == 1:
                #     self._real_d_type = ctypes.c_char * ctypes.sizeof(self._real_d_type)
                #     self._mode = 2  # is bytes
                else:
                    self._mode = 3  # is data array
            elif issubclass(self._real_d_type, _ctypes._SimpleCData):
                self._mode = 4  # is simple data
            else:
                self._mode = 0
        return self._real_d_type

    def __get__(self, instance: MemStruct, owner) -> _t:
        if instance is None: return self
        t = self.d_type.from_address(ctypes.addressof(instance) + self.offset)
        if self._mode == 2 or self._mode == 4: return t.value
        return t

    def __set__(self, instance: MemStruct, value: _t) -> None:
        if instance is None: return
        t = ctypes.cast(ctypes.addressof(instance) + self.offset, ctypes.POINTER(self.d_type))
        if self._mode == 1:
            t[0].set(value)
        elif self._mode == 2:
            t[0].value = value
        elif self._mode == 3:
            t[0][:len(value)] = value
        else:
            t[0] = value

    def __add__(self, offset: int):
        new_f = copy.deepcopy(self)
        new_f.offset += offset
        return new_f


class MaskVar(MemStruct):
    _btype_: any
    _mask_: any


def bit_mask(b_type, mask_size):
    return init_mem_struct(type('_t', (MaskVar,), {
        '_btype_': b_type,
        '_size_': ctypes.sizeof(b_type),
        'value': field(b_type, 0),
        '_mask_': (2 ** mask_size) - 1
    }))


class ShiftField(Field):
    def __init__(self, d_type: Type[_t] | str, offset: int | None = None, shifts: int = 0):
        super().__init__(d_type, offset)
        self.shifts = shifts

    def __get__(self, instance: MemStruct, owner) -> _t:
        if instance is None: return self
        return self.d_type.from_address(ctypes.addressof(instance) + self.offset).value >> self.shifts & self.d_type._mask_

    def __set__(self, instance: MemStruct, value: _t) -> None:
        if instance is None: return
        v = self.d_type.from_address(ctypes.addressof(instance) + self.offset)
        v.value = (v.value & ~(self.d_type._mask_ << self.shifts)) | (value << self.shifts)


def field(d_type: Type[_t] | str, offset: int | None = None, shifts=0) -> _t:
    return ShiftField(d_type, offset, shifts) if shifts or (inspect.isclass(d_type) and issubclass(d_type, MaskVar)) else Field(d_type, offset)


def create_hook(address, res_type, arg_types, func):
    raise NotImplementedError()


class _FuncType:
    _func_type = None
    _real_args_type = None
    _real_res_type = None

    def __init__(self, v: int = 0, res_type=ctypes.c_void_p, args_type=None):
        if args_type is None: args_type = []
        self.v = v
        self._res_type = res_type
        self._args_type = args_type

    def _update_res_type(self):
        self._real_res_type = import_type(self._res_type) if isinstance(self._res_type, str) else self._res_type

    def _update_args_type(self):
        self._real_args_type = [import_type(a) if isinstance(a, str) else a for a in self._args_type]

    def _update_func_type(self):
        self._func_type = ctypes.CFUNCTYPE(self.res_type, ctypes.c_void_p, *self.args_type)

    @property
    def func_type(self):
        if self._func_type is None: self._update_func_type()
        return self._func_type

    @property
    def res_type(self):
        if self._real_res_type is None: self._update_res_type()
        return self._real_res_type

    @property
    def args_type(self):
        if self._real_args_type is None: self._update_args_type()
        return self._real_args_type

    @res_type.setter
    def res_type(self, value):
        self._res_type = value
        self._update_res_type()
        self._update_func_type()

    @args_type.setter
    def args_type(self, value):
        self._args_type = value
        self._update_args_type()
        self._update_func_type()


class _StructFuncType(_FuncType):
    _func_type = None

    def __init__(self, v: int = 0, res_type=ctypes.c_void_p, args_type=None):
        super().__init__(v, res_type, args_type)

        class _Func:
            def __init__(_self, instance):
                _self.instance = instance

            def __call__(_self, *args):
                return self.func_type(self.get_func_address(
                    _self.instance
                ))(ctypes.addressof(
                    _self.instance
                ), *args)

            def hook(_self, func):
                return create_hook(self.get_func_address(
                    _self.instance
                ), self._res_type, self._args_type, func)

        self._make_func = _Func

    def get_func_address(self, instance):
        raise NotImplementedError()

    def __get__(self, instance: MemStruct, owner):
        if instance is None: return self
        return self._make_func(instance)


c_void_p_p_p = ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))


class VTableFunc(_StructFuncType):
    _offset_ = 0

    def get_func_address(self, instance):
        return ctypes.cast(ctypes.addressof(instance.vtable) + self._offset_, c_void_p_p_p)[0][self.v]


class ClassFunc(_StructFuncType):
    def get_func_address(self, instance):
        return self.v


class CFunc(_FuncType):
    def __call__(self, *args):
        return self.func_type(self.v)(*args)

    def hook(self, func):
        return create_hook(self.v, self._res_type, self._args_type, func)


def init_mem_struct(cls: Type[_t]) -> Type[_t]:
    # TODO: sort none offset fields
    fields = []

    _f = []
    for k in dir(cls):
        v = getattr(cls, k)
        if isinstance(v, Field):
            _f.append((k, v))

    current_offset = 0
    for k, v in sorted(_f, key=lambda x: x[1]._fid):
        type_size = 0 if isinstance(v._d_type, str) and cls._size_ is not None else ctypes.sizeof(v.d_type)
        if v.offset is None:
            v.offset = current_offset
            current_offset += type_size
        else:
            current_offset = max(current_offset, v.offset + type_size)
        fields.append(k)

    if cls._size_ is None:
        _size_ = current_offset
    else:
        _size_ = max(cls._size_, current_offset)
    add_size = _size_ - ctypes.sizeof(cls)
    attr = {'_p_field': fields, '_size_': _size_, }
    if add_size > 0: attr['_fields_'] = [('_buf_', ctypes.c_byte * add_size)]
    return type(cls.__name__, (cls,), attr)


class Enumerate:
    def __init__(self, v: int):
        self.value = v


class Enum(MemStruct):
    _type_ = ctypes.c_int
    _value_name_map = {}
    _name_value_map = {}

    def __init__(self, v):
        super().__init__()
        self.set(v)

    @classmethod
    def get_name(cls, value):
        return cls._value_name_map.get(value, value)

    @classmethod
    def get_value(cls, name):
        return cls._name_value_map.get(name, 0)

    @property
    def name(self):
        return self.get_name(self.value)

    def _get_data(self, max_lv=10, lv=0):
        return self.name

    def __str__(self):
        return str(self.name)

    def __eq__(self, other):
        return self.value == other or self.name == other

    def set(self, v):
        if isinstance(v, Enum): v = v.value
        self.value = self._name_value_map.get(v, v)


def init_enum(cls: Type[_t]) -> Type[_t]:
    cls._value_name_map = {}
    cls._name_value_map = {}
    attrs = {'_fields_': [('value', cls._type_)]}
    for k, v in cls.__dict__.items():
        if isinstance(v, Enumerate):
            cls._value_name_map[v.value] = k
            cls._name_value_map[k] = v.value
            attrs[k] = v.value
    return type(cls.__name__, (cls,), attrs)
