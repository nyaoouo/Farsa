from ctypes import *
from inspect import stack
from typing import Annotated, List

try:
    from . import EasyHook
except ImportError:
    import EasyHook

RAISE_ERROR = False


def default_orig(*args): return args


class Hook(object):
    """
    a hook class to do local hooks

    ```restype```, ```argtypes``` and ```hook_function``` need to be overridden
    """
    restype: Annotated[any, "the return type of hook function"] = c_void_p
    argtypes: Annotated[List[any], "the argument types of hook function"] = []
    original: Annotated[callable, "the original function"]
    is_enabled: Annotated[bool, "is the hook enabled"]
    is_installed: Annotated[bool, "is the hook installed"]
    IS_WIN_FUNC = False

    def hook_function(self, *args):
        """
        the hooked function
        """
        return self.original(*args)

    def __init__(self, func_address: int):
        """
        create a hook,remember to install and enable it afterwards and uninstall it after use

        :param func_address: address of the function need to be hooked
        """
        self.address = func_address
        self.is_enabled = False
        self.is_installed = False
        self.hook_info = c_void_p()
        self._hook_function = c_void_p()

        self.original = default_orig
        self.ACL_entries = (c_ulong * 1)(1)
        caller = stack()[1]
        self.create_at = f"{caller.filename}:{caller.lineno}"

    def install(self) -> None:
        """
        install the hook
        """

        if self.is_installed:
            if RAISE_ERROR:
                raise Exception("Hook is installed")
            else:
                return
        self.hook_info = EasyHook.HOOK_TRACE_INFO()
        interface = (WINFUNCTYPE if self.IS_WIN_FUNC else CFUNCTYPE)(self.restype, *self.argtypes)

        def _hook_function(*args):
            return self.hook_function(*args)

        self._hook_function = interface(_hook_function)
        if EasyHook.lh_install_hook(self.address, self._hook_function, None, byref(self.hook_info)):
            raise EasyHook.LocalHookError()

        self.is_installed = True

        original_func_p = c_void_p()
        if EasyHook.lh_get_bypass_address(byref(self.hook_info), byref(original_func_p)):
            raise EasyHook.LocalHookError()
        self.original = interface(original_func_p.value)

    def uninstall(self) -> None:
        """
        uninstall the hook
        """
        if not self.is_installed:
            if RAISE_ERROR:
                raise Exception("Hook is not installed")
            else:
                return
        EasyHook.lh_uninstall_hook(byref(self.hook_info))
        EasyHook.lh_wait_for_pending_removals()
        self.is_installed = False

    def enable(self) -> None:
        """
        enable the hook
        """
        if not self.is_installed:
            if RAISE_ERROR:
                raise Exception("Hook is not installed")
            else:
                return
        if EasyHook.lh_set_exclusive_acl(byref(self.ACL_entries), 1, byref(self.hook_info)):
            raise EasyHook.LocalHookError()
        self.is_enabled = True

    def disable(self) -> None:
        """
        disable the hook
        """
        if not self.is_installed:
            if RAISE_ERROR:
                raise Exception("Hook is not installed")
            else:
                return
        if EasyHook.lh_set_inclusive_acl(byref(self.ACL_entries), 1, byref(self.hook_info)):
            raise EasyHook.LocalHookError()
        self.is_enabled = False

    def install_and_enable(self):
        self.install()
        self.enable()

    def __del__(self):
        try:
            self.uninstall()
        except Exception:
            pass


if __name__ == '__main__':
    from ctypes.wintypes import *

    t_dll = CDLL('User32.dll')
    t_dll.MessageBoxW.argtypes = [HWND, LPCWSTR, LPCWSTR, UINT]
    t_dll.MessageBoxW.restype = INT


    def test(): t_dll.MessageBoxW(None, 'hi content!', 'hi title!', 0)


    class MessageBoxHook(Hook):
        argtypes = [HWND, LPCWSTR, LPCWSTR, UINT]
        restype = INT

        def hook_function(self, handle, title, message, flag):
            res = self.original(handle, "hooked " + title, "hooked " + message, flag)
            print(f"hooked: {title} - {message}, return {res}")
            return res


    test()

    hook = MessageBoxHook(t_dll.MessageBoxW)
    hook.install_and_enable()
    test()

    hook.uninstall()
    test()
