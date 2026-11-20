import glob as _glob
import os as _os
import sys as _sys

# onnxruntime / OpenCV wheels are built with MSVC 14.40+. On Windows machines whose system
# Visual C++ runtime is older, importing them segfaults. The `msvc-runtime` wheel ships current
# DLLs into the venv root; loading them by full path first makes later imports bind to them.
if _sys.platform == "win32":
    import ctypes as _ctypes

    for _dll in sorted(_glob.glob(_os.path.join(_sys.prefix, "*.dll"))):
        try:
            _ctypes.WinDLL(_dll)
        except OSError:
            pass
