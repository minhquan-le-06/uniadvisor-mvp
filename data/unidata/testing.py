"""Pytest fixtures shared by both test folders (data/tests, backend/tests): the tiny simulated world and a marker
for tests that need the real database. Each folder's conftest.py imports them."""

import pytest

from unidata import db as database
from unidata.paths import DB


@pytest.fixture(scope="session")
def tiny_db():
    """The hand-sized simulated world (unidata.sim.tiny): fast, always available, known contents."""
    from unidata.sim import tiny

    return tiny.build(seed=0)


@pytest.fixture
def use_tiny(tiny_db):
    """Make the tiny world what get_db() returns (app, API, rules defaults) for one test."""
    database.set_default(tiny_db)
    yield tiny_db
    database.set_default(None)


needs_real_db = pytest.mark.skipif(not (DB / "manifest.json").exists(), reason="no real database: run `uniadvisor build`")
