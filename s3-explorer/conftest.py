"""Pytest configuration.

Ensures the 'src' directory is in the python path for tests.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _add_to_syspath(path: Path) -> None:
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

_add_to_syspath(SRC)
