import ctypes
import functools
import inspect
from importlib import import_module


@functools.cache
def import_type(type_str: str | bytes):
    if isinstance(type_str, str): type_str = type_str.encode()
    type_str = type_str.strip()
    if type_str[-1] == 42:
        return ctypes.POINTER(import_type(type_str[:-1]))
    if type_str[-1] == 93:
        i = 1
        for i in range(2, len(type_str)):
            if 48 <= type_str[-i] <= 57: continue
        return import_type(type_str[:-(i + 1)]) * int(type_str[-i:-1])
    module_name, attr_name = type_str.split(b':', 1)
    assert inspect.isclass(d_type := eval(attr_name, import_module(module_name).__dict__)), TypeError(f'{type_str} is not a class')
    return d_type
