from __future__ import annotations

from pathlib import Path

import pytest

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> bytes:
    return (_FIXTURES_DIR / name).read_bytes()


@pytest.fixture
def fixture_loader():
    return load_fixture
