import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "contents"))
sys.path.insert(0, str(ROOT / "tests"))

import nr_rundeck  # noqa: E402
from fakeapi import FakeNodeRings  # noqa: E402


@pytest.fixture
def fake():
    return FakeNodeRings()


@pytest.fixture
def env():
    """What Rundeck passes to a script: every plugin setting as RD_CONFIG_<NAME>."""
    return {"RD_CONFIG_API_TOKEN": "test-token"}


@pytest.fixture
def client(fake, env):
    return nr_rundeck.client(env, opener=fake, sleep=lambda _s: None)
