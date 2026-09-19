"""Maschinen und Maschinentypen."""
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session, selectinload

from calc import (
    BILLING_MODES, BILLING_SHEET, BILLING_TIME, machine_rate_breakdown, recommended_sheet_price, sheet_cost_estimate,
)
from common import (
    bad_request, get_machine_types, machine_to_json, parse_money,
)
from core import templates
from database import get_db
from models import (
    Machine, MachineType, ProductMachine, load_calc_settings,
)

router = APIRouter()


def parse_machine_form(db: Session, name, machine_type_id, billing_mode, description,
                       depreciation_euro, lifespan_hours, power_w, cost_per_sheet) -> dict:
    """Prüft die Eingaben. Zeitkosten sind bei Abrechnung nach Zeit Pflicht (fehlende Werte: Standard),
    bei Bogen-Maschinen nur, wenn das Formular sie mitschickt. Der Bogenpreis ist bei Bogen-Abrechnung Pflicht."""
    name = (name or "").strip()
    if not name:
        bad_request("Bitte einen Maschinennamen angeben.")
    if not db.query(MachineType).filter(MachineType.id == machine_type_id).first():
        bad_request("Unbekannter Maschinentyp.")
    if billing_mode not in BILLING_MODES:
        bad_request("Unbekannte Abrechnungsart.")

    sheet_price = None
    if cost_per_sheet is not None and str(cost_per_sheet).strip() != "":
        sheet_price = parse_money(cost_per_sheet, "Kosten pro Bogen")
    if billing_mode == BILLING_SHEET and not sheet_price:
        bad_request("Bei Abrechnung pro Bogen muss der Preis pro Bogen angegeben werden.")

    time_given = any((v or "").strip() for v in (depreciation_euro, lifespan_hours, power_w))
    time_costs = None
    if time_given or billing_mode == BILLING_TIME:
        time_costs = {
            "depreciation_euro": parse_money(depreciation_euro, "Abschreibung"),
            "lifespan_hours": parse_money(lifespan_hours, "Lebensdauer", default=Decimal(1), allow_zero=False),
            "power_w": parse_money(power_w, "Stromverbrauch"),
        }

    return {
        "name": name,
        "machine_type_id": machine_type_id,
        "billing_mode": billing_mode,
        "description": description,
        "time_costs": time_costs,
        "sheet_price": sheet_price,
    }


def apply_machine_form(machine: Machine, values: dict) -> None:
    machine.name = values["name"]
    machine.machine_type_id = values["machine_type_id"]
    machine.billing_mode = values["billing_mode"]
    machine.description = values["description"]
    if values["time_costs"]:
        machine.set_time_costs(**values["time_costs"])
    else:
        machine.time_costs = None
    machine.set_sheet_cost(values["sheet_price"])

@router.get("/machines", response_class=HTMLResponse)
async def list_machines(request: Request, error: str = "", db: Session = Depends(get_db)):
    """Liste aller Maschinen; Sortieren und Filtern passiert im Browser (Spaltenköpfe)."""
    machines = (db.query(Machine)
                .options(selectinload(Machine.machine_type), selectinload(Machine.time_costs), selectinload(Machine.sheet_costs))
                .order_by(Machine.name).all())
    return templates.TemplateResponse("machines/list.html", {
        "request": request,
        "machines": machines,
        "electricity_price": load_calc_settings(db).electricity_price_kwh,
        "error_msg": error
    })


@router.get("/machines/new", response_class=HTMLResponse)
async def new_machine_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neue Maschine"""
    return templates.TemplateResponse("machines/form.html", {
        "request": request,
        "machine": None,
        "machine_types": get_machine_types(db),
        "electricity_price": float(load_calc_settings(db).electricity_price_kwh),
        "title": "Neue Maschine"
    })


@router.post("/machines")
async def create_machine(
    request: Request,
    name: str = Form(...),
    machine_type_id: int = Form(...),
    billing_mode: str = Form(BILLING_TIME),
    description: str = Form(""),
    depreciation_euro: str = Form(""),
    lifespan_hours: str = Form(""),
    power_w: str = Form(""),
    cost_per_sheet: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neue Maschine erstellen"""
    values = parse_machine_form(db, name, machine_type_id, billing_mode, description,
                                depreciation_euro, lifespan_hours, power_w, cost_per_sheet)
    machine = Machine()
    apply_machine_form(machine, values)
    db.add(machine)
    db.commit()
    return RedirectResponse(url="/machines", status_code=303)


@router.post("/api/machines")
async def create_machine_json(
    name: str = Form(...),
    machine_type_id: int = Form(...),
    billing_mode: str = Form(BILLING_TIME),
    description: str = Form(""),
    depreciation_euro: str = Form(""),
    lifespan_hours: str = Form(""),
    power_w: str = Form(""),
    cost_per_sheet: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neue Maschine erstellen und als JSON zurückgeben (für den Dialog im Produkt-Formular)"""
    try:
        values = parse_machine_form(db, name, machine_type_id, billing_mode, description,
                                    depreciation_euro, lifespan_hours, power_w, cost_per_sheet)
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    machine = Machine()
    apply_machine_form(machine, values)
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return JSONResponse(machine_to_json(machine), status_code=201)


@router.get("/api/machine-rate")
async def api_machine_rate(
    depreciation_euro: str = "0",
    lifespan_hours: str = "1",
    power_w: str = "0",
    minutes_per_sheet: str = "2.5",
    wear_cost: str = "0.07",
    db: Session = Depends(get_db)
):
    """Stundensatz einer Maschine (Strom + Abschreibung) und Herleitung der Bogenkosten für die Formulare.
    Rechnet mit dem aktuellen Strompreis aus den Einstellungen; nichts wird gespeichert."""
    electricity_price = load_calc_settings(db).electricity_price_kwh
    try:
        depreciation = parse_money(depreciation_euro, "Abschreibung")
        lifespan = parse_money(lifespan_hours, "Lebensdauer", default=Decimal(1))
        power = parse_money(power_w, "Stromverbrauch")
        minutes = parse_money(minutes_per_sheet, "Laufzeit pro Bogen")
        wear = parse_money(wear_cost, "Verschleiß")
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    total, strom, abschreibung = machine_rate_breakdown(depreciation, lifespan, power, electricity_price)
    sheet_machine, sheet_min = sheet_cost_estimate(total, minutes, wear)
    return {
        "cost_per_hour": float(total), "power_cost": float(strom), "depreciation_cost": float(abschreibung),
        "sheet_machine_cost": float(sheet_machine), "sheet_min_cost": float(sheet_min),
        "recommended_sheet_price": float(recommended_sheet_price(sheet_min)),
    }


@router.get("/machines/{machine_id}/edit", response_class=HTMLResponse)
async def edit_machine_form(machine_id: int, request: Request, db: Session = Depends(get_db)):
    """Maschine bearbeiten"""
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")

    return templates.TemplateResponse("machines/form.html", {
        "request": request,
        "machine": machine,
        "machine_types": get_machine_types(db),
        "electricity_price": float(load_calc_settings(db).electricity_price_kwh),
        "title": "Maschine bearbeiten"
    })


@router.post("/machines/{machine_id}/update")
async def update_machine(
    machine_id: int,
    request: Request,
    name: str = Form(...),
    machine_type_id: int = Form(...),
    billing_mode: str = Form(BILLING_TIME),
    description: str = Form(""),
    depreciation_euro: str = Form(""),
    lifespan_hours: str = Form(""),
    power_w: str = Form(""),
    cost_per_sheet: str = Form(""),
    db: Session = Depends(get_db)
):
    """Maschine aktualisieren"""
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")

    values = parse_machine_form(db, name, machine_type_id, billing_mode, description,
                                depreciation_euro, lifespan_hours, power_w, cost_per_sheet)
    apply_machine_form(machine, values)
    machine.updated_at = datetime.utcnow()

    db.commit()
    return RedirectResponse(url="/machines", status_code=303)


@router.post("/machines/{machine_id}/delete")
async def delete_machine(machine_id: int, db: Session = Depends(get_db)):
    """Maschine löschen (nur wenn kein Produkt sie verwendet)"""
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")

    usage = db.query(ProductMachine).filter(ProductMachine.machine_id == machine_id).count()
    if usage:
        return RedirectResponse(
            url=f"/machines?error=„{machine.name}“ wird in {usage} Produkt-Zeile(n) verwendet und kann nicht gelöscht werden.",
            status_code=303)

    db.delete(machine)
    db.commit()
    return RedirectResponse(url="/machines", status_code=303)


@router.get("/api/machine-types")
async def api_get_machine_types(db: Session = Depends(get_db)):
    """Alle Maschinentypen als JSON (für das Nachladen im Maschinenformular)"""
    return [
        {"id": t.id, "name": t.name, "default_billing_mode": t.default_billing_mode}
        for t in get_machine_types(db)
    ]


@router.post("/api/machine-types/quick-add")
async def api_quick_add_machine_type(
    name: str = Form(...),
    default_billing_mode: str = Form(BILLING_TIME),
    db: Session = Depends(get_db)
):
    """Legt schnell einen neuen Maschinentyp an"""
    name_clean = name.strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="Name darf nicht leer sein")
    if default_billing_mode not in BILLING_MODES:
        raise HTTPException(status_code=400, detail="Unbekannte Abrechnungsart")

    mtype = db.query(MachineType).filter(MachineType.name == name_clean).first()
    if not mtype:
        next_order = (db.query(MachineType).count() or 0)
        mtype = MachineType(name=name_clean, default_billing_mode=default_billing_mode, sort_order=next_order)
        db.add(mtype)
        db.commit()
        db.refresh(mtype)

    return {
        "success": True,
        "id": mtype.id,
        "machine_types": [
            {"id": t.id, "name": t.name, "default_billing_mode": t.default_billing_mode}
            for t in get_machine_types(db)
        ]
    }
