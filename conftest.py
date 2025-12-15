"""Pytest configuration.

This repo keeps importable packages under:
- `src/` (e.g., `shared`)
- `src/modules/` (e.g., `ingestion`, `s3_explore`)

When running tests directly (without installing as a package), ensure those
directories are on `sys.path` so imports work during test collection.
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
MODULES = SRC / "modules"

_add_to_syspath(SRC)
_add_to_syspath(MODULES)
