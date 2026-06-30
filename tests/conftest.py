"""Shared pytest fixtures for the MATSS test suite."""

import pytest

from matss.config import load_content
from matss.determinism import RandomSource


@pytest.fixture
def content():
    """The default validated world content."""
    return load_content()


@pytest.fixture
def rng():
    return RandomSource(seed=1234)


@pytest.fixture
def seed():
    return 1234
