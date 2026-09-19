"""Picobellu Kalkulator - App-Start: Datenbank vorbereiten und Router einbinden."""
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from database import SessionLocal, upgrade_database
from seed import seed_defaults


def prepare_database(max_retries: int = 30, retry_delay: int = 2) -> None:
    """Wartet auf die Datenbank, migriert das Schema und legt fehlende Standard-Stammdaten an."""
    for attempt in range(1, max_retries + 1):
        try:
            upgrade_database()
            print("Database connected and schema is up to date!")
            db = SessionLocal()
            try:
                seed_defaults(db)
            finally:
                db.close()
            return
        except OperationalError:
            print(f"Database not ready yet (attempt {attempt}/{max_retries}). Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    print("Could not connect to database after maximum retries!")
    raise Exception("Database connection failed")


prepare_database()

from routers import dashboard, events, feedback, machines, materials, products, settings, tools  # noqa: E402

app = FastAPI(title="Picobellu Kalkulator")
app.mount("/static", StaticFiles(directory="assets"), name="static")

for module in (dashboard, materials, machines, products, events, feedback, tools, settings):
    app.include_router(module.router)
