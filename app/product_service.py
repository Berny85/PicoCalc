"""Produkt-Service: Formulareingaben prüfen, auf ein Produkt anwenden und den Kalkulator-Kontext bauen."""
from decimal import Decimal
from itertools import zip_longest
from typing import Annotated
import json

from fastapi import Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

import calc
from common import (
    bad_request, get_categories, get_config_value, get_machine_types, get_material_types, machine_to_json,
    material_to_json, parse_money,
)
from models import (
    Category, Machine, Material, Product, ProductLabor, ProductMachine, ProductMaterial, ProductPackaging,
    load_calc_settings, machine_type_label,
)
from seed import FALLBACK_CATEGORY
from units import units_for_json


NonNegative = Annotated[Decimal, Field(ge=0)]


class MaterialLineIn(BaseModel):
    key: str | None = None      # wird unverändert zurückgegeben, damit das Formular die Zeile zuordnen kann
    material_id: int
    amount: NonNegative


class MachineLineIn(BaseModel):
    key: str | None = None
    machine_id: int
    value: NonNegative


class LaborLineIn(BaseModel):
    key: str | None = None
    description: str = ""
    minutes: NonNegative
    hourly_rate: NonNegative


class CalculationIn(BaseModel):
    """Eingaben des Produktkalkulators für die Live-Vorschau (noch nicht gespeichert)."""
    yield_qty: Annotated[int, Field(ge=1)] = 1
    selling_price: NonNegative | None = None
    materials: list[MaterialLineIn] = []
    machines: list[MachineLineIn] = []
    labor: list[LaborLineIn] = []
    packaging: list[MaterialLineIn] = []    # Menge pro Verkaufseinheit


def preview_costs(db: Session, data: CalculationIn) -> dict:
    """Kalkulation für ungespeicherte Eingaben: dieselbe Rechnung wie beim gespeicherten Produkt
    (``calc.calculate_product`` mit den Einstellungen aus der Config)."""
    material_ids = {l.material_id for l in data.materials} | {l.material_id for l in data.packaging}
    materials = {m.id: m for m in db.query(Material).filter(Material.id.in_(material_ids)).all()}
    machines = {
        m.id: m for m in db.query(Machine).options(
            selectinload(Machine.machine_type), selectinload(Machine.time_costs), selectinload(Machine.sheet_costs))
        .filter(Machine.id.in_({l.machine_id for l in data.machines})).all()
    }
    for line in data.materials + data.packaging:
        if line.material_id not in materials:
            bad_request("Material nicht gefunden.")
    for line in data.machines:
        if line.machine_id not in machines:
            bad_request("Maschine nicht gefunden.")

    product = calc.ProductInput(
        yield_qty=data.yield_qty,
        selling_price=data.selling_price,
        materials=tuple(materials[l.material_id].to_input(l.amount) for l in data.materials),
        machines=tuple(machines[l.machine_id].to_input(l.value) for l in data.machines),
        labor=tuple(
            calc.LaborInput(minutes=l.minutes, hourly_rate=l.hourly_rate, description=l.description)
            for l in data.labor
        ),
        packaging=tuple(materials[l.material_id].to_input(l.amount) for l in data.packaging),
    )
    view = calc.costs_to_view(calc.calculate_product(product, load_calc_settings(db)))
    for name, lines in (("materials", data.materials), ("machines", data.machines),
                        ("labor", data.labor), ("packaging", data.packaging)):
        for row, line in zip(view[name], lines):
            row["key"] = line.key
    view["type_label"] = machine_type_label(machines[l.machine_id] for l in data.machines)
    return view


PRODUCT_LOAD_OPTIONS = (
    selectinload(Product.category),
    selectinload(Product.material_links).selectinload(ProductMaterial.material),
    selectinload(Product.machine_links).selectinload(ProductMachine.machine).options(
        selectinload(Machine.machine_type), selectinload(Machine.time_costs), selectinload(Machine.sheet_costs),
    ),
    selectinload(Product.labor_steps),
    selectinload(Product.packaging_links).selectinload(ProductPackaging.material),
)


def parse_product_form(
    db: Session, *, name, category_id, notes, batch_yield, shipping_cost, selling_price, is_for_market,
    used_material_id, used_material_amount, used_machine_id, used_machine_value,
    used_labor_description, used_labor_minutes, used_labor_rate, used_packaging_id, used_packaging_amount,
) -> dict:
    """Prüft die Eingaben des Produktformulars und liefert fertige Werte (Fehler -> HTTP 400)."""
    name = (name or "").strip()
    if not name:
        bad_request("Bitte einen Produktnamen angeben.")

    yield_qty = int(parse_money(batch_yield, "Ausbeute", default=Decimal(1)))
    if yield_qty < 1:
        bad_request("Die Ausbeute muss mindestens 1 sein.")

    category = None
    if category_id:
        category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        category = db.query(Category).filter(Category.name == FALLBACK_CATEGORY).first()

    def collect(ids, values, model, label):
        rows = []
        for raw_id, raw_value in zip(ids, values):
            if not (raw_id and str(raw_id).strip() and raw_value and str(raw_value).strip()):
                continue
            try:
                entity_id = int(str(raw_id).strip())
            except ValueError:
                bad_request(f"Ungültige {label}-Auswahl.")
            value = parse_money(raw_value, f"Menge ({label})")
            if value > 0:
                if not db.query(model).filter(model.id == entity_id).first():
                    bad_request(f"{label} nicht gefunden.")
                rows.append((entity_id, value))
        return rows

    labor = []
    for description, raw_minutes, raw_rate in zip_longest(
            used_labor_description, used_labor_minutes, used_labor_rate, fillvalue=""):
        if not str(raw_minutes).strip():
            continue
        minutes = parse_money(raw_minutes, "Arbeitszeit")
        if minutes > 0:
            labor.append({
                "description": (description or "").strip(),
                "minutes": minutes,
                "hourly_rate": parse_money(raw_rate, "Stundensatz"),
            })

    price = parse_money(selling_price, "Verkaufspreis") if selling_price else Decimal(0)

    return {
        "name": name,
        "category_id": category.id if category else None,
        "notes": notes,
        "yield_qty": yield_qty,
        "shipping_cost": parse_money(shipping_cost, "Versandkosten"),
        "selling_price": price if price > 0 else None,
        "is_for_market": is_for_market in ("1", "true", "on"),
        "materials": collect(used_material_id, used_material_amount, Material, "Material"),
        "machines": collect(used_machine_id, used_machine_value, Machine, "Maschine"),
        "labor": labor,
        "packaging": collect(used_packaging_id, used_packaging_amount, Material, "Verpackungsmaterial"),
    }


def apply_product_form(product: Product, data: dict) -> None:
    for key in ("name", "category_id", "notes", "yield_qty", "shipping_cost", "selling_price", "is_for_market"):
        setattr(product, key, data[key])
    product.material_links = [
        ProductMaterial(material_id=mid, amount=amount, sort_order=i)
        for i, (mid, amount) in enumerate(data["materials"])
    ]
    product.machine_links = [
        ProductMachine(machine_id=mid, value=value, sort_order=i)
        for i, (mid, value) in enumerate(data["machines"])
    ]
    product.labor_steps = [
        ProductLabor(description=step["description"] or None, minutes=step["minutes"],
                     hourly_rate=step["hourly_rate"], sort_order=i)
        for i, step in enumerate(data["labor"])
    ]
    product.packaging_links = [
        ProductPackaging(material_id=mid, amount=amount, sort_order=i)
        for i, (mid, amount) in enumerate(data["packaging"])
    ]


def product_form_context(db: Session, request: Request, product: Product | None = None) -> dict:
    """Gemeinsamer Kontext für Neu-/Bearbeiten-Formular des Produkt-Kalkulators"""
    settings = load_calc_settings(db)
    materials = db.query(Material).options(
        selectinload(Material.material_type), selectinload(Material.brand)).order_by(Material.name).all()
    machines = db.query(Machine).options(selectinload(Machine.machine_type)).order_by(Machine.name).all()

    context = {
        "request": request,
        "product": product,
        "categories": get_categories(db),
        "material_types": get_material_types(db),
        "machine_types": get_machine_types(db),
        "units": units_for_json(),
        "default_labor_rate": get_config_value(db, "labor_rate_per_hour", "20.00"),
        "margin_multiplier": float(settings.margin_multiplier),
        "materials_json": json.dumps([material_to_json(m) for m in materials]),
        "machines_json": json.dumps([machine_to_json(m) for m in machines]),
        "initial_materials_json": "[]",
        "initial_machines_json": "[]",
        "initial_labor_json": "[]",
        "initial_packaging_json": "[]",
        "title": "Neues Produkt kalkulieren",
    }
    if product:
        context["initial_materials_json"] = json.dumps(
            [{"id": l.material_id, "amount": float(l.amount)} for l in product.material_links])
        context["initial_machines_json"] = json.dumps(
            [{"id": l.machine_id, "value": float(l.value)} for l in product.machine_links])
        context["initial_labor_json"] = json.dumps(
            [{"description": s.description or "", "minutes": float(s.minutes), "rate": float(s.hourly_rate)}
             for s in product.labor_steps])
        context["initial_packaging_json"] = json.dumps(
            [{"id": l.material_id, "amount": float(l.amount)} for l in product.packaging_links])
        context["title"] = f"Produkt bearbeiten: {product.name}"
    return context