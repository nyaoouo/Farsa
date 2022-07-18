import time
import sys
import win32pipe, win32file, pywintypes


def pipe_server(key):
    print("pipe server")
    count = 0
    pipe = win32pipe.CreateNamedPipe(
        r'\\.\pipe\\' + key,
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
        1, 65536, 65536,
        0,
        None)
    try:
        print("waiting for client")
        win32pipe.ConnectNamedPipe(pipe, None)
        print("got client")

        while count < 10:
            print(f"writing message {count}")
            # convert to bytes
            some_data = str.encode(f"{count}")
            win32file.WriteFile(pipe, some_data)
            time.sleep(1)
            count += 1

        print("finished now")
    finally:
        win32file.CloseHandle(pipe)


def pipe_client(key: str):
    print("pipe client")
    quit = False

    while not quit:
        try:
            handle = win32file.CreateFile(
                r'\\.\pipe\\' + key,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            res = win32pipe.SetNamedPipeHandleState(handle, win32pipe.PIPE_READMODE_MESSAGE, None, None)
            if res == 0:
                print(f"SetNamedPipeHandleState return code: {res}")
            while True:
                resp = win32file.ReadFile(handle, 64 * 1024)
                print(f"message: {resp}")
        except pywintypes.error as e:
            if e.args[0] == 2:
                print("no pipe, trying again in a sec")
                time.sleep(1)
            elif e.args[0] == 109:
                print("broken pipe, bye bye")
                quit = True


if __name__ == '__main__':
   import threading
   t1 = threading.Thread(target=pipe_server,args=('py_pipe_test',))
   t2 = threading.Thread(target=pipe_client,args=('py_pipe_test',))
   t3 = threading.Thread(target=pipe_client,args=('py_pipe_test',))
   t1.start()
   t2.start()
   t3.start()
   t1.join()
   t2.join()
   t3.join()
