import copy
import ctypes
import typing
import functools
from farsa.hook import Hook
from .utils import import_type

_t = typing.TypeVar('_t')


class FuncWrap(typing.Generic[_t]):
    def __init__(self, func_p, res_type: typing.Type[_t], args_type, instance=None, offset=0):
        self.func_p = func_p
        self.res_type = res_type
        self.instance = instance
        self.offset = offset
        self.args_type = args_type if instance is None else ([ctypes.c_void_p] + args_type)
        self.c_func = ctypes.CFUNCTYPE(res_type, *self.args_type)(func_p)
        # print(res_type, self.args_type, self.c_func,self.offset)

    def __call__(self, *args) -> _t:
        return self.c_func(*args) if self.instance is None else self.c_func(ctypes.byref(self.instance, self.offset), *args)

    def hook(self, func) -> Hook:
        return type(func.__name__, (Hook,), {
            'restype': self.res_type,
            'argstype': self.args_type,
            'hook_function': func
        })(self.func_p)

    def __add__(self, other):
        f = copy.deepcopy(self)
        f.offset += other
        return f


class Func(typing.Generic[_t]):
    def __init__(
            self,
            get_func_address: typing.Callable[[typing.Any, typing.Any], int] | int,
            res_type: typing.Type[_t] = ctypes.c_void_p,
            args_type=None,
            is_instance_func=False,
            cache_level=1,  # 0: no cache, 1: cache instance, 2: cache owner
            offset=0,
    ):
        self.get_func_address = get_func_address
        self.is_instance_func = is_instance_func
        self._res_type = res_type
        self._args_type = args_type or []
        self._name = None
        self.cache_level = cache_level
        self.offset = offset

    def __set_name__(self, owner, name):
        owner._m_funcs_[name] = self
        self._name = name

    @functools.cached_property
    def res_type(self):
        return import_type(self._res_type) if isinstance(self._res_type, str) else self._res_type

    @functools.cached_property
    def args_type(self):
        return [import_type(a) if isinstance(a, str) else a for a in self._args_type]

    def __get__(self, instance, owner) -> 'FuncWrap[_t] | _FuncType':
        if instance is None and (instance := getattr(owner, 'instance', None)) is None:
            return self
        if addr := (self.get_func_address(instance, owner) if callable(self.get_func_address) else self.get_func_address):
            wrapper = FuncWrap(addr, self.res_type, self.args_type, instance, self.offset) if self.is_instance_func else FuncWrap(addr, self.res_type, self.args_type)
            if self.cache_level == 2:
                setattr(owner, self._name, wrapper)
            elif self.cache_level == 1:
                setattr(instance, self._name, wrapper)
            return wrapper

    def __add__(self, other):
        f = copy.deepcopy(self)
        f.offset += other
        return f


def func(res_type=ctypes.c_void_p, args_type=None, is_instance_func=False, cache_level=1, offset=0, ):
    return lambda f: Func(f, res_type, args_type, is_instance_func, cache_level, offset)
