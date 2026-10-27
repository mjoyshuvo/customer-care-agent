import pytest
from sqlalchemy import text

from ccare.db.engine import get_engine, session_factory
from ccare.seed import data


@pytest.fixture(scope="session")
def engine():
    eng = get_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:  # pragma: no cover
        pytest.skip(
            f"Postgres not reachable ({exc}); run: docker compose -f deploy/compose/compose.yaml up -d"
        )
    return eng


@pytest.fixture
def db(engine):
    """A freshly seeded database for each test."""
    Session = session_factory(engine)
    with Session() as s, s.begin():
        data.load(s)
    with Session() as s:
        yield s
