"""FocsOCR — a line-level text recogniser tuned for lecture boards, slides and pen-tablet notes."""
import glob as _glob
import os as _os
import sys as _sys

__version__ = "1.0.0"

# PyTorch >= 2.4 needs MSVC runtime >= 14.40. Many Windows PCs still have 14.2x in System32,
# which makes `import torch` fail with WinError 1114. The `msvc-runtime` wheel drops current
# DLLs into the venv root; loading them by full path first makes every later import bind to them.
if _sys.platform == "win32":
    import ctypes as _ctypes

    for _dll in sorted(_glob.glob(_os.path.join(_sys.prefix, "*.dll"))):
        try:
            _ctypes.WinDLL(_dll)
        except OSError:
            pass
