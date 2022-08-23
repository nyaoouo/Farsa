import ctypes
import enum
from typing import Dict


class EnumMeta(type(ctypes.Structure)):
    @classmethod
    def __prepare__(metacls, name, bases, **kwargs):
        res = super().__prepare__(name, bases, **kwargs)
        res['_name_map'] = {}
        res['_value_map'] = {}
        return res

    def __new__(cls, name, bases, namespace, **kwargs):
        try:
            if Enum in bases:
                namespace['_fields_'] = [('value', namespace.get('_base_', Enum._base_))]
        except NameError:
            pass
        return super().__new__(cls, name, bases, namespace, **kwargs)


class Enum(ctypes.Structure, metaclass=EnumMeta):
    _base_ = ctypes.c_int
    _name_map: Dict[int, str] = {}
    _value_map: Dict[str, int] = {}
    _default_name: str = None
    _default_value: int = None
    value: int

    def __init__(self, value=None):
        if value is None: value = self._default_value
        super(Enum, self).__init__(value=value)

    def __class_getitem__(cls, item):
        return cls(cls.get_name(item))

    def __repr__(self):
        return self.__class__.__name__ + '.' + self.name

    @property
    def name(self) -> str:
        return self._name_map.get(self.value, self._default_name)

    @name.setter
    def name(self, val: str):
        self.value = self.get_value(val)

    @classmethod
    def get_name(cls, value: int) -> str:
        return cls._name_map.get(value, cls._default_name)

    @classmethod
    def get_value(cls, value: str) -> int:
        return cls._value_map.get(value, cls._default_value)

    def __add__(self, other):
        v = self.__class__.from_buffer_copy(self)
        v.value += other
        return v

    def __mul__(self, other):
        v = self.__class__.from_buffer_copy(self)
        v.value *= other
        return v

    def __eq__(self, other):
        if isinstance(other, (Enum, enum.Enum)):
            return self.value == other.value
        if isinstance(other, int):
            return self.value == other
        if isinstance(other, str):
            return self.name == other
        return False

    def __hash__(self):
        return hash(self.value)

    def __int__(self):
        return self.value

    def __str__(self):
        return self.name


class Enumerate:
    def __init__(self, value=None):
        self.value = value
        self.name = ''
        self.class_name = ''

    def __set_name__(self, owner: Enum, name):
        if self.name: return
        self.class_name = owner.__class__.__name__
        self.name = name
        if self.value is None:
            if values := list(owner._value_map.values()):
                self.value = values[-1] + 1
            else:
                self.value = 0
        if isinstance(self.value, Enumerate):
            self.value = self.value.value
        owner._name_map.setdefault(self.value, name)
        owner._value_map[name] = self.value
        owner._default_name = name
        owner._default_value = self.value

    def __repr__(self):
        return self.class_name + '.' + self.name

    def __get__(self, instance, owner):
        return self.value

    def __set__(self, instance, value):
        pass
