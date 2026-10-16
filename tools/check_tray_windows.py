"""Check the state of NetVisual's tray windows via Win32 API."""
import ctypes
import ctypes.wintypes as wt

u = ctypes.WinDLL("user32", use_last_error=True)
u.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
u.FindWindowW.restype = wt.HWND
u.IsWindowVisible.argtypes = [wt.HWND]
u.IsWindowVisible.restype = wt.BOOL
u.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
u.GetWindowRect.restype = wt.BOOL

for name in ("TopLevelWindowForOverflowXamlIsland", "NetVisualTrayWindow"):
    hwnd = u.FindWindowW(name, None)
    vis = bool(u.IsWindowVisible(hwnd)) if hwnd else False
    if hwnd:
        r = wt.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        rect = f"({r.left},{r.top},{r.right},{r.bottom})"
    else:
        rect = "-"
    print(f"{name}: hwnd={hwnd} visible={vis} rect={rect}")
