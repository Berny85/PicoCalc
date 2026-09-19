"""Tests gegen eine echte PostgreSQL-Datenbank (Schema, Migration, Rundung, Bedarfsrechnung).

Die Fixtures (schema, db) und die Schutzregel für ``*_test``-Datenbanken stehen in conftest.py.
"""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from database import APP_DIR
from models import (
    Brand, Category, Config, EventItem, Machine, MachineSheetCost, MachineTimeCost, MachineType, Material,
    MaterialPrice, MaterialType, MarketEvent, Product, ProductLabor, ProductMachine, ProductMaterial,
    ProductPackaging,
)
from calc import BILLING_SHEET, BILLING_TIME
from seed import seed_defaults  # noqa: F401 (im Test direkt aufgerufen)

D = Decimal

pytestmark = pytest.mark.usefixtures("schema")


def make_machine(db, name="Drucker", mode=BILLING_TIME, depreciation_euro=0, lifespan_hours=1, power_w=0,
                 cost_per_sheet=None, with_time_costs=None):
    mtype = db.query(MachineType).filter(MachineType.name == ("3D-Drucker" if mode == BILLING_TIME else "Schneideplotter")).one()
    machine = Machine(name=name, machine_type_id=mtype.id, billing_mode=mode)
    if with_time_costs if with_time_costs is not None else mode == BILLING_TIME:
        machine.set_time_costs(depreciation_euro, lifespan_hours, power_w)
    machine.set_sheet_cost(cost_per_sheet)
    db.add(machine)
    db.flush()
    return machine


def make_material(db, name, unit, price, type_key="filament", brand=None):
    mtype = db.query(MaterialType).filter(MaterialType.key == type_key).one()
    material = Material(name=name, material_type_id=mtype.id, unit=unit, brand=brand)
    material.set_price(price)
    db.add(material)
    db.flush()
    return material


def make_product(db, materials=(), machines=(), labor=(), packaging=(), **kwargs):
    product = Product(name=kwargs.pop("name", "Testprodukt"), **kwargs)
    product.material_links = [ProductMaterial(material_id=m.id, amount=a, sort_order=i) for i, (m, a) in enumerate(materials)]
    product.machine_links = [ProductMachine(machine_id=m.id, value=v, sort_order=i) for i, (m, v) in enumerate(machines)]
    product.labor_steps = [
        ProductLabor(description=d, minutes=mins, hourly_rate=rate, sort_order=i) for i, (d, mins, rate) in enumerate(labor)
    ]
    product.packaging_links = [ProductPackaging(material_id=m.id, amount=a, sort_order=i) for i, (m, a) in enumerate(packaging)]
    db.add(product)
    db.flush()
    return product


def test_migration_matches_models():
    """Das Alembic-Schema muss exakt den Models entsprechen (kein vergessener Migrationsschritt)."""
    from alembic import command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig(str(APP_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(APP_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False
    command.check(cfg)  # wirft bei Abweichungen


def test_seed_defaults_are_created_once(db):
    seed_defaults(db)
    assert db.query(Category).count() == 8
    assert db.query(MachineType).count() == 6
    assert db.query(MaterialType).count() == 4


# --------------------------------------------------------------------------- Materialien: Preis-Historie, Marken

def test_material_price_keeps_four_decimals(db):
    # Regression: Numeric(10,2) machte aus 0,235 € pro Bogen 0,24 €
    material = make_material(db, "Sticker", "sheet", D("0.2355"), "sticker_sheet")
    db.commit()
    db.expire_all()
    assert db.get(Material, material.id).price_per_unit == D("0.2355")


def test_price_history_keeps_old_prices_and_the_latest_one_applies(db):
    material = make_material(db, "PLA", "kg", D("20"))
    db.commit()
    # gleicher Preis -> kein neuer Historieneintrag
    material.set_price(D("20"))
    db.commit()
    assert db.query(MaterialPrice).filter_by(material_id=material.id).count() == 1

    # neuer Preis (mit späterem Zeitstempel) -> zweiter Eintrag, der neueste gilt
    material.prices.append(MaterialPrice(price=D("22.5"), valid_from=datetime.utcnow() + timedelta(seconds=5)))
    db.commit()
    db.expire_all()
    material = db.get(Material, material.id)
    assert material.price_per_unit == D("22.5")
    assert [p.price for p in material.prices] == [D("22.5"), D("20")]   # neueste zuerst


def test_price_change_flows_into_existing_products(db):
    pla = make_material(db, "PLA", "kg", D("20"))
    product = make_product(db, materials=[(pla, 100)])                     # 100 g
    db.commit()
    assert db.get(Product, product.id).calculate_costs()["batch_material_cost"] == 2.0

    pla.prices.append(MaterialPrice(price=D("30"), valid_from=datetime.utcnow() + timedelta(seconds=5)))
    db.commit()
    db.expire_all()
    assert db.get(Product, product.id).calculate_costs()["batch_material_cost"] == 3.0


def test_materials_can_be_sorted_by_their_current_price(db):
    make_material(db, "Teuer", "kg", D("30"))
    make_material(db, "Billig", "kg", D("10"))
    db.commit()
    names = [m.name for m in db.query(Material).order_by(Material.price_per_unit).all()]
    assert names == ["Billig", "Teuer"]


def test_brand_is_shared_and_deleting_it_keeps_the_material(db):
    brand = Brand(name="Prusament")
    db.add(brand)
    a = make_material(db, "PLA schwarz", "kg", D("25"), brand=brand)
    b = make_material(db, "PLA weiß", "kg", D("25"), brand=brand)
    db.commit()
    assert a.brand_name == b.brand_name == "Prusament"
    assert db.query(Brand).count() == 1

    db.delete(brand)
    db.commit()
    db.expire_all()
    assert db.get(Material, a.id).brand is None and db.get(Material, a.id).brand_name == ""


def test_deleting_a_material_removes_its_price_history(db):
    material = make_material(db, "Frei", "kg", D("5"))
    db.commit()
    db.delete(material)
    db.commit()
    assert db.query(MaterialPrice).count() == 0


def test_negative_price_is_rejected(db):
    material = make_material(db, "X", "kg", D("1"))
    db.commit()
    db.add(MaterialPrice(material_id=material.id, price=D("-1")))
    with pytest.raises(IntegrityError):
        db.commit()


# --------------------------------------------------------------------------- Maschinen: Kosten in eigenen Tabellen

def test_machine_power_keeps_fractional_watts(db):
    machine = make_machine(db, power_w=D("7.5"), depreciation_euro=D(100), lifespan_hours=D(1000))
    db.commit()
    db.expire_all()
    assert db.get(Machine, machine.id).power_w == D("7.5")


def test_sheet_machine_needs_no_time_costs_and_falls_back_to_defaults(db):
    plotter = make_machine(db, "Plotter", BILLING_SHEET, cost_per_sheet=D("0.12"))
    db.commit()
    db.expire_all()
    plotter = db.get(Machine, plotter.id)
    assert plotter.time_costs is None and plotter.sheet_costs.cost_per_sheet == D("0.12")
    assert (plotter.depreciation_euro, plotter.lifespan_hours, plotter.power_w) == (0, 1, 0)
    assert plotter.cost_per_sheet == D("0.12")


def test_time_machine_can_drop_its_sheet_price(db):
    machine = make_machine(db, cost_per_sheet=D("0.10"), depreciation_euro=100, lifespan_hours=100)
    db.commit()
    assert db.query(MachineSheetCost).count() == 1
    machine.set_sheet_cost(None)
    db.commit()
    assert db.query(MachineSheetCost).count() == 0
    assert db.get(Machine, machine.id).cost_per_sheet is None


def test_deleting_a_machine_removes_its_cost_rows(db):
    machine = make_machine(db, cost_per_sheet=D("0.10"), depreciation_euro=100, lifespan_hours=100)
    db.commit()
    db.delete(machine)
    db.commit()
    assert db.query(MachineTimeCost).count() == 0 and db.query(MachineSheetCost).count() == 0


def test_zero_lifespan_and_negative_costs_are_rejected(db):
    machine = make_machine(db)
    db.commit()
    machine.time_costs.lifespan_hours = 0
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    machine = db.get(Machine, machine.id)
    machine.time_costs.power_w = -1
    with pytest.raises(IntegrityError):
        db.commit()


# --------------------------------------------------------------------------- Produkte

def test_product_costs_from_database_rows(db):
    pla = make_material(db, "PLA", "kg", D("20"))
    rot = make_material(db, "PLA rot", "kg", D("11.90"))
    beutel = make_material(db, "Beutel", "piece", D("0.10"), "other")
    printer = make_machine(db, depreciation_euro=D(350), lifespan_hours=D(3000), power_w=D(100))
    product = make_product(
        db, materials=[(pla, 40), (rot, 100)], machines=[(printer, 120)],
        labor=[("Montage", 10, 24)], packaging=[(beutel, 1)], yield_qty=4,
    )
    db.commit()
    db.expire_all()

    costs = db.get(Product, product.id).calculate_costs()
    # Material: 40 g * 20 €/kg + 100 g * 11,90 €/kg = 0,80 + 1,19 (zweites Filament ohne Rundungsverlust)
    assert costs["batch_material_cost"] == 1.99
    assert costs["yield_qty"] == 4
    assert [l["name"] for l in costs["materials"]] == ["PLA", "PLA rot"]
    assert costs["batch_labor_cost"] == 4.0 and costs["labor"][0]["description"] == "Montage"
    assert costs["packaging_cost"] == 0.1 and costs["packaging"][0]["name"] == "Beutel"


def test_labor_steps_are_summed(db):
    product = make_product(db, labor=[("Entgraten", 30, 20), ("Montage", 15, 40)])
    db.commit()
    db.expire_all()
    product = db.get(Product, product.id)
    assert product.labor_minutes == D(45)
    assert product.calculate_costs()["batch_labor_cost"] == 20.0


def test_packaging_follows_the_material_price_and_is_per_piece(db):
    beutel = make_material(db, "Beutel", "piece", D("0.10"), "other")
    product = make_product(db, packaging=[(beutel, 2)], yield_qty=10)
    db.commit()
    assert db.get(Product, product.id).calculate_costs()["packaging_cost"] == 0.2   # nicht durch die Ausbeute geteilt

    beutel.prices.append(MaterialPrice(price=D("0.25"), valid_from=datetime.utcnow() + timedelta(seconds=5)))
    db.commit()
    db.expire_all()
    assert db.get(Product, product.id).calculate_costs()["packaging_cost"] == 0.5


def test_config_values_drive_the_calculation(db):
    printer = make_machine(db, depreciation_euro=D(0), lifespan_hours=D(1), power_w=D(1000))
    product = make_product(db, machines=[(printer, 60)])
    db.add(Config(key="electricity_price_kwh", value="0,50"))
    db.commit()
    assert db.get(Product, product.id).calculate_costs()["batch_machine_cost"] == 0.5


def test_deleting_a_product_removes_all_its_lines(db):
    pla = make_material(db, "PLA", "kg", D("20"))
    printer = make_machine(db)
    product = make_product(db, materials=[(pla, 10)], machines=[(printer, 5)], labor=[("x", 5, 20)], packaging=[(pla, 1)])
    db.commit()
    db.delete(product)
    db.commit()
    for model in (ProductMaterial, ProductMachine, ProductLabor, ProductPackaging):
        assert db.query(model).count() == 0
    assert db.query(Material).count() == 1


def test_used_material_cannot_be_deleted_at_db_level(db):
    pla = make_material(db, "PLA", "kg", D("20"))
    make_product(db, materials=[(pla, 10)])
    db.commit()
    db.delete(pla)
    with pytest.raises(IntegrityError):
        db.commit()


def test_material_used_only_as_packaging_cannot_be_deleted_either(db):
    beutel = make_material(db, "Beutel", "piece", D("0.1"), "other")
    make_product(db, packaging=[(beutel, 1)])
    db.commit()
    db.delete(beutel)
    with pytest.raises(IntegrityError):
        db.commit()


def test_invalid_billing_mode_and_yield_are_rejected(db):
    mtype = db.query(MachineType).first()
    db.add(Machine(name="X", machine_type_id=mtype.id, billing_mode="kaputt"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(Product(name="Y", yield_qty=0))
    with pytest.raises(IntegrityError):
        db.commit()


def test_negative_labor_is_rejected(db):
    product = make_product(db)
    db.commit()
    db.add(ProductLabor(product_id=product.id, minutes=-5, hourly_rate=20))
    with pytest.raises(IntegrityError):
        db.commit()


# --------------------------------------------------------------------------- Events

def test_event_totals_count_whole_batches(db):
    pla = make_material(db, "PLA", "kg", D("20"))
    karton = make_material(db, "Karte", "piece", D("0.10"), "other")
    printer = make_machine(db)
    plotter = make_machine(db, name="Plotter", mode=BILLING_SHEET, cost_per_sheet=D("0.12"))
    # Ausbeute 3, pro Charge: 30 g Filament, 2 Karten, 90 Min Druck, 4 Bögen, 30 Min Arbeit (in zwei Schritten)
    product = make_product(
        db, materials=[(pla, 30), (karton, 2)], machines=[(printer, 90), (plotter, 4)],
        labor=[("Entgraten", 10, 20), ("Montage", 20, 20)], yield_qty=3,
    )
    event = MarketEvent(name="Markt")
    db.add(event)
    db.flush()
    db.add(EventItem(event_id=event.id, product_id=product.id, target_quantity=8))  # 8 Stück -> 3 Chargen
    db.commit()
    db.expire_all()

    totals = db.get(MarketEvent, event.id).calculate_totals()
    assert totals["filament_breakdown"] == {"PLA": 90.0}         # 3 x 30 g (nicht 8 x 30 g)
    assert totals["total_filament_weight_g"] == 90.0
    assert totals["other_breakdown"] == [{"name": "Karte", "unit": "Stück", "amount": 6.0}]
    assert totals["total_print_time_hours"] == 4.5               # 3 x 90 min
    assert totals["total_machine_sheets"] == 12.0
    assert totals["total_labor_hours"] == 1.5                    # 3 x (10 + 20) min
    assert totals["total_target_units"] == 8
