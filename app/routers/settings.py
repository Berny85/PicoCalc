"""Globale Einstellungen (Strompreis, Marge, Maschinentypen)."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from calc import BILLING_SHEET, BILLING_TIME
from common import (
    get_config_value, get_machine_types, set_config_value,
)
from core import templates
from database import get_db
from models import (
    Machine, MachineType, STROM_PREIS_KWH,
)

router = APIRouter()


def parse_machine_type_lines(text: str) -> list[tuple[str, str]]:
    """Zeilen wie „Schneideplotter | Bogen“ -> [(Name, Abrechnungsart)]; ohne Zusatz gilt Zeit."""
    result = []
    seen = set()
    for line in text.replace("\r", "").split("\n"):
        name, _, mode_text = line.partition("|")
        name = name.strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        mode = BILLING_SHEET if mode_text.strip().lower() in ("bogen", "sheet") else BILLING_TIME
        result.append((name, mode))
    return result


def machine_types_to_text(types: list[MachineType]) -> str:
    return "\n".join(
        f"{t.name} | Bogen" if t.default_billing_mode == BILLING_SHEET else t.name for t in types
    )


def sync_machine_types(db: Session, wanted: list[tuple[str, str]]) -> None:
    existing = {t.name: t for t in db.query(MachineType).all()}
    names = [name for name, _ in wanted]
    for i, (name, mode) in enumerate(wanted):
        if name in existing:
            existing[name].sort_order = i
            existing[name].default_billing_mode = mode
        else:
            db.add(MachineType(name=name, default_billing_mode=mode, sort_order=i))
    for name, mtype in existing.items():
        if name not in names and not db.query(Machine).filter(Machine.machine_type_id == mtype.id).count():
            db.delete(mtype)


@router.get("/settings", response_class=HTMLResponse)
async def view_settings(
    request: Request,
    success: str = "",
    db: Session = Depends(get_db)
):
    """Globale Einstellungen anzeigen"""
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "electricity_price_kwh": get_config_value(db, "electricity_price_kwh", str(STROM_PREIS_KWH)),
        "labor_rate_per_hour": get_config_value(db, "labor_rate_per_hour", "20.00"),
        "margin_multiplier": get_config_value(db, "margin_multiplier", "2.0"),
        "company_name": get_config_value(db, "company_name", "Picobellu Design"),
        "machine_types_text": machine_types_to_text(get_machine_types(db)),
        "success": bool(success)
    })


@router.post("/settings")
async def save_settings(
    request: Request,
    electricity_price_kwh: str = Form("0.22"),
    labor_rate_per_hour: str = Form("20.00"),
    margin_multiplier: str = Form("2.0"),
    company_name: str = Form("Picobellu Design"),
    machine_types: str = Form(""),
    db: Session = Depends(get_db)
):
    """Globale Einstellungen speichern"""
    set_config_value(db, "electricity_price_kwh", electricity_price_kwh.replace(',', '.').strip(), "Strompreis in €/kWh", "pricing")
    set_config_value(db, "labor_rate_per_hour", labor_rate_per_hour.replace(',', '.').strip(), "Standard-Stundensatz Arbeit in €/h", "pricing")
    set_config_value(db, "margin_multiplier", margin_multiplier.replace(',', '.').strip(), "Standard-Marge (Aufschlagsfaktor)", "pricing")
    set_config_value(db, "company_name", company_name.strip(), "Name des Unternehmens/Shops", "general")

    # Maschinentypen (eine pro Zeile, optional „| Bogen“)
    wanted_types = parse_machine_type_lines(machine_types)
    if wanted_types:
        sync_machine_types(db, wanted_types)

    db.commit()
    return RedirectResponse(url="/settings?success=1", status_code=303)
