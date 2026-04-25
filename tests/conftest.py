from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _qt_offscreen() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
