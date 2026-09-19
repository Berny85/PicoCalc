"""Gemeinsame Fixtures für Tests mit Datenbank.

Diese Tests laufen nur, wenn DATABASE_URL auf eine Datenbank zeigt, deren Name auf ``_test`` endet -
so kann nie versehentlich die Entwicklungs- oder Produktivdatenbank geleert werden:

    docker compose run --rm --no-deps \\
        -e DATABASE_URL=postgresql://printuser:printpass@db:5432/printcalc_test \\
        -e FILE_STORAGE_PATH=/tmp/storage web pytest
"""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from database import Base, SessionLocal, engine, upgrade_database
from seed import seed_defaults


@pytest.fixture(scope="module")
def schema():
    """Frisches Schema per Alembic (einmal pro Testdatei)."""
    if not engine.url.database or not engine.url.database.endswith("_test"):
        pytest.skip("DATABASE_URL zeigt nicht auf eine *_test-Datenbank")
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    except OperationalError:
        pytest.skip("Testdatenbank nicht erreichbar")
    upgrade_database()
    yield


@pytest.fixture()
def clean_db(schema):
    """Leere Tabellen mit Standard-Stammdaten; räumt nach jedem Test wieder auf."""
    session = SessionLocal()
    seed_defaults(session)
    session.close()
    try:
        yield
    finally:
        with engine.begin() as conn:
            tables = [t.name for t in Base.metadata.sorted_tables]
            conn.execute(text("TRUNCATE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))


@pytest.fixture()
def db(clean_db):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
