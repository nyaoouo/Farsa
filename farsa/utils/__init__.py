import threading
import time


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
        self.count = start-1
        self.lock = threading.Lock()

    def get(self):
        with self.lock:
            self.count += 1
            return self.count
