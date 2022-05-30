import _ctypes
import ctypes
from inspect import isclass
from typing import TypeVar, TYPE_CHECKING, Type
from farsa.struct.base import MemStruct, Field, get_data, ShiftField, Enum
from farsa.winapi import kernel32, structure
from ..exception import WinAPIError

if TYPE_CHECKING:
    from .. import Process

_t = TypeVar('_t')


class Remote:
    def __init__(self, process: 'Process', address: int):
        self.process = process
        self.address = address

    def copy(self, address: int = None) -> 'Remote':
        return Remote(self.process, address or self.address)


class RemoteField(Field):
    def __init__(self, d_type: Type[_t] | str, offset: int):
        super().__init__(d_type, offset)
        self.is_remote_type = isclass(d_type) and issubclass(d_type, RemoteMemStruct)

    def __get__(self, instance: 'RemoteMemStruct', owner) -> _t:
        if instance is None: return self
        address = instance.remote.address + self.offset
        if self.is_remote_type:
            try:
                return self.d_type(remote=instance.remote.copy(address))
            except TypeError:
                pass
        if kernel32.ReadProcessMemory(
                instance.remote.process.handle,
                address,
                ctypes.addressof(instance) + self.offset,
                ctypes.sizeof(self.d_type),
                None
        ):
            return Field.__get__(self, instance, owner)
        raise WinAPIError(kernel32.GetLastError(), "ReadProcessMemory")

    def __set__(self, instance: 'RemoteMemStruct', value: _t) -> None:
        if instance is None: return
        if isinstance(value, RemoteMemStruct):
            update_remote_struct_buffer(value)
        Field.__set__(self, instance, value)
        # print(f"write {instance.remote.address + self.offset:x} from {ctypes.addressof(instance) + self.offset:x}")
        if not kernel32.WriteProcessMemory(
                instance.remote.process.handle,
                instance.remote.address + self.offset,
                ctypes.addressof(instance) + self.offset,
                ctypes.sizeof(self.d_type),
                None
        ):
            raise WinAPIError(kernel32.GetLastError(), "WriteProcessMemory")


class RemoteShiftField(ShiftField):
    def __init__(self, d_type: Type[_t] | str, offset: int, shifts: int):
        super().__init__(d_type, offset, shifts)
        self.is_remote_type = isclass(d_type) and issubclass(d_type, RemoteMemStruct)

    def __get__(self, instance: 'RemoteMemStruct', owner) -> _t:
        if instance is None: return self
        address = instance.remote.address + self.offset
        if kernel32.ReadProcessMemory(
                instance.remote.process.handle,
                address,
                ctypes.addressof(instance) + self.offset,
                ctypes.sizeof(self.d_type),
                None
        ):
            return ShiftField.__get__(self, instance, owner)
        raise WinAPIError(kernel32.GetLastError(), "ReadProcessMemory")

    def __set__(self, instance: 'RemoteMemStruct', value: _t) -> None:
        if instance is None: return
        ShiftField.__set__(self, instance, value)
        # print(f"write {instance.remote.address + self.offset:x} from {ctypes.addressof(instance) + self.offset:x}")
        if not kernel32.WriteProcessMemory(
                instance.remote.process.handle,
                instance.remote.address + self.offset,
                ctypes.addressof(instance) + self.offset,
                ctypes.sizeof(self.d_type),
                None
        ):
            raise WinAPIError(kernel32.GetLastError(), "WriteProcessMemory")


class RemoteMemStruct(MemStruct):
    def __init__(self, *args, remote: Remote, **kwargs):
        super().__init__(**kwargs)
        self.remote = remote

    def __rshift__(self, other):
        r = self.remote.process.read(other, self.remote.address)
        # print(type(r))
        return r


class RemotePointer(RemoteMemStruct):
    _fields_ = [('_address', structure.c_address)]
    address = RemoteField(structure.c_address, 0)
    _type_: Type[_t]

    def __init__(self, remote: Remote):
        super().__init__(remote=remote)
        self._address = remote.address

        if issubclass(self._type_, Enum):
            self._mode = 1
        elif issubclass(self._type_, _ctypes.Array):
            if self._type_._type_ == ctypes.c_char or self._type_._type_ == ctypes.c_wchar:
                self._mode = 2
            else:
                self._mode = 3
        else:
            self._mode = 0

    def iter_till_trim(self):
        i = 0
        while True:
            try:
                yield self[i]
            except Exception as e:
                break
            i += 1

    def get_value(self):
        return list(self.iter_till_trim())


    def __getitem__(self, item) -> _t:
        if isinstance(item, int):
            address = self.address
            if not address: raise ValueError("reading from empty pointer")
            address += item * ctypes.sizeof(self._type_)
            d = self.remote.process.read(self._type_, address)
            if isinstance(d, RemoteMemStruct):
                d.remote = self.remote.copy(address)
            return d
        elif isinstance(item, slice):
            return [self[i] for i in range(*item.indices(item.stop))]
        raise TypeError("Only integer indexing is supported")

    def __setitem__(self, key, value):
        raise NotImplementedError("RemotePointer is read-only")

    def __bool__(self):
        return bool(self.address)

    def __repr__(self):
        return f"<RemotePointer {self.address:x}>"

    def _get_data(self, max_lv=10, lv=0):
        return self.__repr__()


class RemoteArray(RemoteMemStruct):
    _fields_: Field  # need to be defined when init
    _type_: Type[_t]
    _length_: int

    def __getitem__(self, item) -> _t:
        if isinstance(item, int):
            address = self.remote.address + item * ctypes.sizeof(self._type_)
            if kernel32.ReadProcessMemory(
                    self.remote.process.handle,
                    address,
                    ctypes.addressof(self) + item * ctypes.sizeof(self._type_),
                    ctypes.sizeof(self._type_),
                    None
            ):
                d = self.remote.process.read(self._type_, address)
                if isinstance(d, RemoteMemStruct):
                    d.remote = self.remote.copy(address)
                return d
            raise WinAPIError(kernel32.GetLastError(), "ReadProcessMemory")
        elif isinstance(item, slice):
            return [self[i] for i in range(*item.indices(self._length_))]
        raise TypeError("Only integer indexing is supported")

    def __setitem__(self, key, value):
        # TODO: Implement
        raise TypeError("Cannot assign to array")

    def __len__(self):
        return self._length_

    def __iter__(self):
        return iter(self[i] for i in range(self._length_))

    def decode(self, encoding: str = 'utf-8', errors: str = 'ignore') -> str:
        if self._type_ is ctypes.c_char:
            d = b''
            for i in range(self._length_):
                d += self[i]
                if d[-1] == 0: return d[:-1].decode(encoding, errors)
            return d.decode(encoding)
        else:
            d = bytearray(self._length_)
            for i in range(self._length_):
                d[i] = self[i]
                if d[i] == 0: break
            return d.decode(encoding)

    @classmethod
    def create_cls(cls, t: Type[_t], size: int):
        return type(f'{cls.__name__}_{t.__name__}', (cls,), {
            '_fields_': [('_buf_', t * size)],
            '_type_': t,
            '_length_': size
        })

    def _get_data(self, max_lv=10, lv=0):
        return [get_data(self[i], max_lv, lv) for i in range(self._length_)]


def update_remote_struct_buffer(remote_struct: RemoteMemStruct):
    if not kernel32.ReadProcessMemory(
            remote_struct.remote.process.handle,
            remote_struct.remote.address,
            ctypes.addressof(remote_struct),
            ctypes.sizeof(remote_struct),
            None
    ):
        raise WinAPIError(kernel32.GetLastError(), "ReadProcessMemory")


def to_remote_type(t: Type[_t], force_array=False) -> Type[_t]:
    if isclass(t):
        if issubclass(t, RemoteMemStruct):
            return t
        elif issubclass(t, _ctypes.Array):
            if not force_array and not issubclass(t._type_, (MemStruct, _ctypes.Array, _ctypes._Pointer)): return t
            return RemoteArray.create_cls(to_remote_type(t._type_), t._length_)
        elif issubclass(t, _ctypes._Pointer):
            return type(t.__name__, (RemotePointer,), {'_type_': to_remote_type(t._type_)})
        elif issubclass(t, MemStruct):
            remote_key = f'__remote_type_{hash(t)}__'
            if not hasattr(t, remote_key):
                n_t = type(f'r_{t.__name__}', (t, RemoteMemStruct), {})
                setattr(t, remote_key, n_t)
                for k in dir(t):
                    v = getattr(t, k)
                    if isinstance(v, ShiftField):
                        setattr(n_t, k, RemoteShiftField(v.d_type, v.offset, v.shifts))
                    elif isinstance(v, Field):
                        setattr(n_t, k, RemoteField(to_remote_type(v.d_type), v.offset))
            return getattr(t, remote_key)
    return t
