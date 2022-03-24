import ctypes
from functools import cached_property
from inspect import isclass
from typing import TypeVar, Type, Tuple
import pefile
from .winapi import kernel32, structure
from .utils import process, memory, network, injection
from .struct.remote import Remote, to_remote_type, RemoteMemStruct
from .pattern import StaticPatternSearcher
from .exception import WinAPIError

_t = TypeVar('_t')

_is_wow_64 = ctypes.sizeof(ctypes.c_void_p) == 4


def wow64(is_wow_64: bool) -> str:
    return 'x86' if is_wow_64 else 'x64'


class ModuleInfo:
    def __init__(self, handle, module_name: bytes):
        self.handle = handle
        self.module_name = module_name
        self._module_info = process.get_module_by_name(handle, module_name)

    @cached_property
    def pattern_scanner(self):
        return StaticPatternSearcher(self.pe)

    @cached_property
    def pe(self):
        return pefile.PE(self._module_info.filename, fast_load=True)

    @cached_property
    def file_path(self) -> bytes:
        return self._module_info.filename

    @property
    def base_address(self) -> int:
        return self._module_info.lpBaseOfDll

    @property
    def module_size(self) -> int:
        return self._module_info.SizeOfImage


class Process:
    def __init__(self, pid: int):
        self.pid = pid
        self.handle = kernel32.OpenProcess(structure.PROCESS.PROCESS_ALL_ACCESS.value, False, pid)
        if not self.handle: raise WinAPIError(kernel32.GetLastError(), 'OpenProcess')
        is_wow_64 = process.process_is_wow64(self.handle)
        if is_wow_64 != _is_wow_64:
            raise Exception(f'Process is in {wow64(is_wow_64)} mode, but this module is in {wow64(_is_wow_64)} mode')
        self._module_info_cache: dict[bytes, ModuleInfo] = {}
        self._base_module: ModuleInfo | None = None
        self._injected_py_base = None

    @classmethod
    def from_name(cls, process_name: str) -> 'Process':
        return cls(process.get_pid_by_name(process_name))

    def __del__(self):
        kernel32.CloseHandle(self.handle)

    def get_module_info(self, module_name: bytes) -> ModuleInfo:
        if module_name not in self._module_info_cache:
            self._module_info_cache[module_name] = ModuleInfo(self.handle, module_name)
        return self._module_info_cache[module_name]

    @property
    def base_module(self) -> ModuleInfo:
        if self._base_module is None:
            self._base_module = self.get_module_info(process.get_base_module(self.handle).name)
        return self._base_module

    def __getitem__(self, item: Tuple[Type[_t], int]) -> _t:
        return self.read(*item)

    def __setitem__(self, item: Tuple[Type[_t], int], value: _t):
        return self.write(*item, value)

    def read(self, d_type: Type[_t], address: int) -> _t:
        _d_type = to_remote_type(d_type)
        if isclass(_d_type) and issubclass(_d_type, RemoteMemStruct):
            return _d_type(remote=Remote(self, address))
        return memory.read_memory(self.handle, d_type, address)

    def write(self, d_type: Type[_t], address: int, value: _t):
        return memory.write_memory(self.handle, address, value)

    def inject_python(self):
        if self._injected_py_base is None:
            self._injected_py_base = injection.get_python_base_address(self.handle, True)
        else:
            raise Exception('Python already injected')

    def exec_shell(self, shell_code: bytes, auto_inject=False):
        py_base_address = self._injected_py_base or injection.get_python_base_address(self.handle, auto_inject)
        shell_code_address = memory.alloc(self.handle, len(shell_code))
        memory.write_string(self.handle, shell_code_address, shell_code)
        process.start_thread(self.handle, py_base_address + injection.func_offsets['PyRun_SimpleString'], shell_code_address)
        # kernel32.VirtualFreeEx(self.handle, shell_code_address, 0, 0x8000)

    def tcp_connections(self):
        return network.find_process_tcp_connections(self.pid)

    def inject_dll(self, dll_path: str):
        return process.inject_dll(self.handle, dll_path)

    def start_thread(self, call_address, params=None):
        return process.start_thread(self.handle, call_address, params)
