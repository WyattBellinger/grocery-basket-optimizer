import json
from pathlib import Path

import pytest


@pytest.fixture
def arguments():
    return json.loads((Path(__file__).parent / "fixtures" / "example.json").read_text())


@pytest.fixture
def expected():
    return json.loads((Path(__file__).parent / "fixtures" / "expected.json").read_text())
