import threading
import time
import traceback
import typing

_T = typing.TypeVar('_T')


class allow_hook:
    class hook_call:
        def __init__(self, stack: list, func):
            self.stack = stack
            self.func = func

        def __call__(self, *args, **kwargs):
            return self.stack.pop()(self, *args, **kwargs) if self.stack else self.func(*args, **kwargs) if self.func else None

    def __init__(self, func=None):
        self.func = func
        self.hooks = []
        self.append = self.hooks.append
        self.remove = self.hooks.remove
        self.insert = self.hooks.insert

    def __call__(self, *args, **kwargs):
        if self.hooks:
            return self.hook_call(self.hooks.copy(), self.func)(*args, **kwargs)
        elif self.func:
            return self.func(*args, **kwargs)


class WaitUntilTimeout(Exception):
    def __init__(self):
        super().__init__('WaitUntilTimeout')


def wait_until(func, timeout=-1, interval=0.1, *args, **kwargs):
    start = time.perf_counter()
    while not func(*args, **kwargs):
        if 0 < timeout < time.perf_counter() - start:
            raise WaitUntilTimeout()
        time.sleep(interval)


class Counter:
    def __init__(self, start=0):
        self.count = start - 1
        self.lock = threading.Lock()

    def get(self):
        with self.lock:
            self.count += 1
            return self.count


def try_run(try_count, exception_type=Exception, print_traceback=2, print_func=print):
    def dec(func):
        def wrapper(*args, **kwargs):
            _try_count = try_count
            while _try_count > 0:
                try:
                    return func(*args, **kwargs)
                except exception_type as e:
                    _try_count -= 1
                    if _try_count:
                        if print_traceback > 1:
                            print_func(f"error: {e}\n{traceback.format_exc()}")
                        if print_traceback > 0:
                            print_func(f"retry {_try_count} times...")
                    else:
                        raise

        return wrapper

    return dec


def arr_to_bytes(arr):
    return bytes(arr).split(b'\0', 1)[0]


def byte_list_flag_set(byte_list, idx, val, item_size=8):
    if val:
        byte_list[idx // item_size] |= 1 << (idx % item_size)
    else:
        byte_list[idx // item_size] &= ~(1 << (idx % item_size))


def byte_list_flag_get(byte_list, idx, item_size=8):
    return (byte_list[idx // item_size] & 1 << (idx % item_size)) > 0


def bit_field_iter(flag):
    i = 0
    while flag:
        if flag & 1: yield i
        flag >>= 1
        i += 1


def bit_field_count(flag):
    i = 0
    while flag:
        if flag & 1: i += 1
        flag >>= 1
    return i


class LazyLoad(typing.Generic[_T]):
    def __init__(self, func: typing.Callable[[typing.Any], _T]):
        self.func = func
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner) -> _T:
        setattr(owner, self.name, (res := self.func(owner)))
        return res


def lazy_load(func: typing.Callable[[typing.Any], _T]) -> _T: return LazyLoad(func)

