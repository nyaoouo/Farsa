import ctypes
from .utils import import_type


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
