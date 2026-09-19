"""Standard-Stammdaten, die eine frische Datenbank braucht (nur wenn die Tabellen leer sind)."""
from sqlalchemy.orm import Session

from calc import BILLING_TIME, BILLING_SHEET
from models import Category, MachineType, MaterialType

DEFAULT_MATERIAL_TYPES = [
    ("filament", "3D-Filament (€/kg)", "Filament für 3D-Drucker", 1),
    ("sticker_sheet", "Sticker-Sheet (€/Bogen)", "Bögen für Sticker", 2),
    ("diecut_sticker", "DieCut-Sticker Material", "Material für einzelne Sticker", 3),
    ("other", "Sonstiges", "Andere Materialien", 99),
]

DEFAULT_MACHINE_TYPES = [
    ("3D-Drucker", BILLING_TIME),
    ("Schneideplotter", BILLING_SHEET),
    ("Tintenstrahl-Drucker", BILLING_SHEET),
    ("Laser / Gravierer", BILLING_TIME),
    ("Transferpresse / Heißpresse", BILLING_TIME),
    ("Sonstiges", BILLING_TIME),
]

DEFAULT_CATEGORIES = [
    "Dekoration", "Technik", "Ersatzteile", "Spielzeug",
    "Werkzeuge", "Sticker", "Papierprodukte", "Sonstiges",
]

FALLBACK_CATEGORY = "Sonstiges"


def seed_defaults(db: Session) -> None:
    if not db.query(MaterialType).first():
        for key, name, desc, sort_order in DEFAULT_MATERIAL_TYPES:
            db.add(MaterialType(key=key, name=name, description=desc, sort_order=sort_order))

    if not db.query(MachineType).first():
        for i, (name, mode) in enumerate(DEFAULT_MACHINE_TYPES):
            db.add(MachineType(name=name, default_billing_mode=mode, sort_order=i))

    if not db.query(Category).first():
        for i, name in enumerate(DEFAULT_CATEGORIES):
            db.add(Category(name=name, sort_order=i))

    db.commit()
