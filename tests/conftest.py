import pytest

from uniadvisor import db as database
from uniadvisor.paths import DB


@pytest.fixture(scope="session")
def tiny_db():
    """The hand-sized simulated world (uniadvisor.sim.tiny): fast, always available, known contents."""
    from uniadvisor.sim import tiny

    return tiny.build(seed=0)


@pytest.fixture
def use_tiny(tiny_db):
    """Make the tiny world what get_db() returns (app, API, rules defaults) for one test."""
    database.set_default(tiny_db)
    yield tiny_db
    database.set_default(None)


needs_real_db = pytest.mark.skipif(not (DB / "manifest.json").exists(), reason="no real database: run `uniadvisor build`")
