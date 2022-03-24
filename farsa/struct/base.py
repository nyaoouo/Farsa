import ctypes
from typing import TypeVar, Type, Iterable

_t = TypeVar('_t')


class MemStruct(ctypes.Structure):
    _pack_ = 1
    __field_list = []


class Field:
    def __init__(self, d_type: Type[_t], offset: int | None = None):
        self.d_type = d_type
        self.offset = offset
        self.key = ''

    def __get__(self, instance: MemStruct, owner) -> _t:
        if instance is None: return self
        return getattr(instance, self.key)

    def __set__(self, instance: MemStruct, value: _t) -> None:
        if instance is None: return
        setattr(instance, self.key, value)


def field(d_type: Type[_t], offset: int | None = None) -> _t:
    return Field(d_type, offset)


def field_sort(attrs: Iterable[tuple[str, any]], require_type=Field) -> tuple[list[tuple[str, Type[_t]]], list[str]]:
    size = 0
    set_fields = []
    pad_count = 0
    field_names = []
    for name, field in attrs:
        if not isinstance(field, require_type): continue
        if field.offset is None:
            field.offset = size
        elif field.offset < size:
            raise ValueError(f'Field {name} offset is less than previous field, {field.offset} < {size}')
        elif field.offset > size:
            pad_size = field.offset - size
            set_fields.append((f'__padding_size_{pad_size}_cnt_{pad_count}', ctypes.c_byte * pad_size))
            pad_count += 1
            size = field.offset
        size += ctypes.sizeof(field.d_type)
        field_key = f'__field_{name}'
        field.key = field_key
        set_fields.append((field_key, field.d_type))
        field_names.append(name)
    return set_fields, field_names


def init_mem_struct(cls: Type[_t]) -> Type[_t]:
    set_fields, field_names = field_sort(cls.__dict__.items())
    return type(cls.__name__, (cls,), {'_fields_': set_fields, '__field_list': field_names})
