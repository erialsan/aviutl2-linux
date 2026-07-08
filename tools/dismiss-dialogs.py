#!/usr/bin/env python3
"""Send Return key events via X11 XTest to dismiss Wine/AviUtl2 startup dialogs.

AviUtl2 shows a "D3D RDMs not supported." dialog (and occasionally a Wine error
dialog) during initialization. This helper presses Return a fixed number of
times with a delay. Use it while the application is launching.
"""

import argparse
import ctypes
import ctypes.util
import time


def send_return(display_name: bytes, count: int, delay: float) -> None:
    libX11_path = ctypes.util.find_library("X11")
    libXtst_path = ctypes.util.find_library("Xtst")
    if not libX11_path or not libXtst_path:
        raise RuntimeError("X11 or Xtst library not found")

    X11 = ctypes.CDLL(libX11_path)
    Xtst = ctypes.CDLL(libXtst_path)

    X11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    X11.XOpenDisplay.restype = ctypes.c_void_p
    X11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    X11.XDefaultRootWindow.restype = ctypes.c_ulong
    X11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    X11.XKeysymToKeycode.restype = ctypes.c_ubyte
    X11.XFlush.argtypes = [ctypes.c_void_p]

    Xtst.XTestFakeKeyEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_int,
        ctypes.c_ulong,
    ]

    XK_Return = 0xFF0D

    display = X11.XOpenDisplay(display_name)
    if not display:
        raise RuntimeError(f"Cannot open display {display_name!r}")

    root = X11.XDefaultRootWindow(display)
    keycode = X11.XKeysymToKeycode(display, XK_Return)

    for i in range(count):
        if i:
            time.sleep(delay)
        Xtst.XTestFakeKeyEvent(display, keycode, 1, 0)
        Xtst.XTestFakeKeyEvent(display, keycode, 0, 0)
        X11.XFlush(display)

    print(f"Sent Return {count} time(s) to display {display_name!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dismiss Wine dialogs with Return")
    parser.add_argument("--display", default=":1", help="X11 display (default: :1)")
    parser.add_argument("--count", type=int, default=2, help="Number of Return presses")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between presses")
    args = parser.parse_args()

    send_return(args.display.encode(), args.count, args.delay)


if __name__ == "__main__":
    main()
