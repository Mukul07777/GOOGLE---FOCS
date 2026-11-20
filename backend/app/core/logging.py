import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s %(name)s  %(message)s", datefmt="%H:%M:%S")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    root = logging.getLogger("focs")
    root.setLevel(level)
    root.handlers[:] = [handler]
    root.propagate = False
