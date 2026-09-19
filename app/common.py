"""Gemeinsame Helfer: Konfigurationswerte, Formular-Parser, Stammdaten-Abfragen, JSON-Darstellung."""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.orm import Session

from calc import dec
from models import (
    Config, Machine, MachineType, Material, MaterialType,
)
from units import MATERIAL_UNITS, unit_factor


def parse_decimal(value: str) -> float:
    """Konvertiert einen String mit Komma oder Punkt als Dezimaltrenner zu float"""
    if value is None or str(value).strip() == '':
        return 0.0
    return float(str(value).replace(',', '.'))


def get_config_value(db: Session, key: str, default: str = None) -> str:
    """Holt einen Konfigurationswert aus der DB oder gibt den Default zurück"""
    cfg = db.query(Config).filter(Config.key == key).first()
    if cfg and cfg.value is not None:
        return cfg.value
    return default


def get_config_float(db: Session, key: str, default: float = 0.0) -> float:
    """Holt einen Konfigurationswert als float"""
    val = get_config_value(db, key, None)
    if val is None:
        return default
    try:
        return parse_decimal(val)
    except (ValueError, TypeError):
        return default


def set_config_value(db: Session, key: str, value: str, description: str = None, category: str = "general"):
    """Setzt oder aktualisiert einen Konfigurationswert"""
    cfg = db.query(Config).filter(Config.key == key).first()
    if not cfg:
        cfg = Config(key=key, value=value, description=description, category=category)
        db.add(cfg)
    else:
        cfg.value = value
        if description:
            cfg.description = description
        if category:
            cfg.category = category
        cfg.updated_at = datetime.utcnow()
    db.commit()


def get_machine_types(db: Session) -> list[MachineType]:
    return db.query(MachineType).order_by(MachineType.sort_order, MachineType.name).all()


def get_material_types(db: Session, only_active: bool = True):
    """Lädt Materialtypen aus der Datenbank"""
    query = db.query(MaterialType)
    if only_active:
        query = query.filter(MaterialType.is_active == 1)
    return query.order_by(MaterialType.sort_order, MaterialType.name).all()


def bad_request(message: str):
    raise HTTPException(status_code=400, detail=message)


def parse_money(value, field: str, default=None, allow_zero=True) -> Decimal:
    """Parst eine Zahl aus einem Formularfeld (Komma oder Punkt); Fehler -> HTTP 400 mit deutscher Meldung"""
    try:
        number = dec(value, default if default is not None else Decimal(0))
    except (InvalidOperation, ValueError):
        bad_request(f"Ungültige Zahl im Feld „{field}“.")
    if number < 0:
        bad_request(f"„{field}“ darf nicht negativ sein.")
    if not allow_zero and number == 0:
        bad_request(f"„{field}“ muss größer als 0 sein.")
    return number


def material_to_json(m: Material) -> dict:
    """Material-Darstellung für die Dropdowns im Produkt-Kalkulator"""
    unit = MATERIAL_UNITS.get(m.unit, {})
    return {
        "id": m.id,
        "name": m.name,
        "material_type": m.material_type.name,
        "brand": m.brand_name,
        "unit": m.unit,
        "price_per_unit": float(m.price_per_unit),
        "price_label": unit.get("price_label", f"€/{m.unit}"),
        "input_label": unit.get("input_label", m.unit),
        "factor": float(unit_factor(m.unit)) if m.unit in MATERIAL_UNITS else 1.0,
    }


def machine_to_json(m: Machine) -> dict:
    """Maschinen-Darstellung für die Dropdowns im Produkt-Kalkulator (Kosten rechnet der Server, siehe /api/calculate)"""
    return {
        "id": m.id,
        "name": m.name,
        "machine_type": m.machine_type.name,
        "billing_mode": m.billing_mode,
    }
