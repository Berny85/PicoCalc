"""Routen-Tests über die echte App (FastAPI TestClient + Testdatenbank).

Sie sichern das Verhalten der gesamten Weboberfläche ab und sind das Sicherheitsnetz für Umbauten
an der Struktur von main.py.
"""
import io
import re

import pytest
from fastapi.testclient import TestClient

from models import Brand, Machine, MachineType, Material, MaterialPrice, MaterialType, Product

pytestmark = pytest.mark.usefixtures("schema")


@pytest.fixture()
def client(clean_db):
    import main  # startet Migration + Seeds gegen die Testdatenbank
    return TestClient(main.app, follow_redirects=False)


# --------------------------------------------------------------------------- Helfer

def material_type_id(db, key="filament"):
    return db.query(MaterialType).filter(MaterialType.key == key).one().id


def machine_type_id(db, name="3D-Drucker"):
    return db.query(MachineType).filter(MachineType.name == name).one().id


def add_material(client, db, name="PLA", unit="kg", price="20", type_key="filament"):
    r = client.post("/api/materials", data={
        "name": name, "material_type_id": material_type_id(db, type_key), "unit": unit, "price_per_unit": price,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def add_machine(client, db, name="Drucker", mode="time", type_name="3D-Drucker", **fields):
    data = {"name": name, "machine_type_id": machine_type_id(db, type_name), "billing_mode": mode}
    data.update(fields)
    r = client.post("/api/machines", data=data)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def product_form(**overrides):
    data = {
        "name": "Testprodukt", "batch_yield": "4", "shipping_cost": "0", "selling_price": "", "is_for_market": "1",
        "used_material_id": [], "used_material_amount": [], "used_machine_id": [], "used_machine_value": [],
        "used_labor_description": ["Montage"], "used_labor_minutes": ["10"], "used_labor_rate": ["24"],
        "used_packaging_id": [], "used_packaging_amount": [],
    }
    data.update(overrides)
    return data


def create_recipe_product(client, db):
    pla = add_material(client, db, "PLA", "kg", "20")
    bogen = add_material(client, db, "Sticker-Bogen", "sheet", "0.50", "sticker_sheet")
    printer = add_machine(client, db, "Drucker", "time", depreciation_euro="350", lifespan_hours="3000", power_w="100")
    plotter = add_machine(client, db, "Plotter", "sheet", "Schneideplotter", cost_per_sheet="0.12")
    beutel = add_material(client, db, "Beutel", "piece", "0.10", "other")
    r = client.post("/products", data=product_form(
        used_packaging_id=[str(beutel)], used_packaging_amount=["1"],
        used_material_id=[str(pla), str(bogen)], used_material_amount=["40", "3"],
        used_machine_id=[str(printer), str(plotter)], used_machine_value=["120", "5"],
    ))
    assert r.status_code == 303, r.text
    product_id = int(re.match(r"/products/(\d+)", r.headers["location"]).group(1))
    return product_id, {"pla": pla, "bogen": bogen, "beutel": beutel, "printer": printer, "plotter": plotter}


# --------------------------------------------------------------------------- Seiten

def test_all_pages_render_on_an_empty_database(client):
    pages = [
        "/", "/materials", "/materials/new", "/material-types", "/material-types/new",
        "/machines", "/machines/new", "/products", "/products/new", "/events", "/events/new",
        "/feedback-ideas", "/feedback-ideas/new", "/settings", "/tools/png-to-svg", "/tools/converted-files",
        "/api/machine-types",
    ]
    for page in pages:
        response = client.get(page)
        assert response.status_code == 200, f"{page}: {response.status_code}"


def test_unknown_ids_return_404(client):
    for page in ["/materials/99/edit", "/machines/99/edit", "/products/99", "/products/99/edit", "/events/99",
                 "/events/99/print", "/feedback-ideas/99/edit", "/material-types/99/edit"]:
        assert client.get(page).status_code == 404, page


# --------------------------------------------------------------------------- Materialien

def test_material_crud_and_delete_guard(client, db):
    r = client.post("/materials", data={
        "name": "Testfilament", "material_type_id": material_type_id(db), "unit": "kg",
        "price_per_unit": "11,90", "brand": "X", "color": "Rot",
    })
    assert r.status_code == 303
    material = db.query(Material).one()
    assert float(material.price_per_unit) == 11.9
    assert material.brand_name == "X" and db.query(Brand).count() == 1

    assert "Testfilament" in client.get("/materials").text
    assert "Testfilament" in client.get(f"/materials/{material.id}/edit").text
    assert client.get("/materials?material_type=filament&sort_by=type&sort_order=desc").status_code == 200

    r = client.post(f"/materials/{material.id}/update", data={
        "name": "Umbenannt", "material_type_id": material_type_id(db), "unit": "sheet", "price_per_unit": "0.2355",
    })
    assert r.status_code == 303
    db.refresh(material)
    assert material.name == "Umbenannt" and material.unit == "sheet" and float(material.price_per_unit) == 0.2355
    assert material.brand_name == ""                       # Marke im Formular geleert
    assert db.query(MaterialPrice).filter_by(material_id=material.id).count() == 2   # 11,90 und 0,2355 stehen in der Historie
    edit = client.get(f"/materials/{material.id}/edit").text
    assert "Preisverlauf" in edit and "11,90" in edit and "0,2355" in edit

    # gleicher Preis, gleiche Marke -> keine Doppelungen
    for _ in range(2):
        client.post(f"/materials/{material.id}/update", data={
            "name": "Umbenannt", "material_type_id": material_type_id(db), "unit": "sheet",
            "price_per_unit": "0.2355", "brand": "Xerox",
        })
    db.expire_all()
    assert db.query(MaterialPrice).filter_by(material_id=material.id).count() == 2
    assert db.query(Brand).filter_by(name="Xerox").count() == 1

    # Verwendetes Material lässt sich nicht löschen, ein freies schon
    product_id, ids = create_recipe_product(client, db)
    r = client.post(f"/materials/{ids['pla']}/delete")
    assert r.status_code == 303 and "error=" in r.headers["location"]
    assert client.post(f"/materials/{material.id}/delete").headers["location"] == "/materials"
    assert db.query(Material).filter(Material.id == material.id).count() == 0


def test_material_json_api_validation(client, db):
    base = {"name": "X", "material_type_id": material_type_id(db), "unit": "kg", "price_per_unit": "1"}
    assert client.post("/api/materials", data=base).status_code == 201
    for override, needle in [({"name": "  "}, "Materialnamen"), ({"unit": "furlong"}, "Einheit"),
                             ({"price_per_unit": "-1"}, "negativ"), ({"price_per_unit": "abc"}, "Ungültige Zahl"),
                             ({"material_type_id": 999}, "Materialtyp")]:
        r = client.post("/api/materials", data={**base, **override})
        assert r.status_code == 400 and needle in r.json()["error"], (override, r.text)


def test_material_types_lifecycle(client, db):
    r = client.post("/material-types", data={"key": "textil", "name": "Textilien", "sort_order": "5"})
    assert r.status_code == 303
    type_id = db.query(MaterialType).filter(MaterialType.key == "textil").one().id
    assert "Textilien" in client.get("/material-types").text
    assert client.post(f"/material-types/{type_id}/update", data={"key": "textil", "name": "Stoffe", "sort_order": "5", "is_active": "1"}).status_code == 303

    # Typ in Verwendung -> nur deaktivieren
    client.post("/api/materials", data={"name": "Filz", "material_type_id": type_id, "unit": "m", "price_per_unit": "3"})
    client.post(f"/material-types/{type_id}/delete")
    db.expire_all()
    assert db.get(MaterialType, type_id).is_active == 0
    # Ohne Materialien -> wirklich löschen
    other = db.query(MaterialType).filter(MaterialType.key == "diecut_sticker").one().id
    client.post(f"/material-types/{other}/delete")
    db.expire_all()
    assert db.get(MaterialType, other) is None


# --------------------------------------------------------------------------- Maschinen

def test_machine_crud_and_guards(client, db):
    r = client.post("/machines", data={
        "name": "Testdrucker", "machine_type_id": machine_type_id(db), "billing_mode": "time",
        "depreciation_euro": "350", "lifespan_hours": "3000", "power_w": "100",
    })
    assert r.status_code == 303
    machine = db.query(Machine).one()
    assert float(machine.power_w) == 100 and machine.billing_mode == "time"
    assert "Testdrucker" in client.get("/machines").text
    assert client.get("/machines?sort_by=type&sort_order=desc").status_code == 200
    assert client.get(f"/machines/{machine.id}/edit").status_code == 200

    r = client.post(f"/machines/{machine.id}/update", data={
        "name": "Plotter", "machine_type_id": machine_type_id(db, "Schneideplotter"), "billing_mode": "sheet",
        "cost_per_sheet": "0.12",
    })
    assert r.status_code == 303
    db.refresh(machine)
    assert machine.billing_mode == "sheet" and float(machine.cost_per_sheet) == 0.12

    # Sheet ohne Preis, ungültige Abrechnung, unbekannter Typ
    base = {"name": "X", "machine_type_id": machine_type_id(db), "billing_mode": "sheet"}
    for override, needle in [({}, "Preis pro Bogen"), ({"billing_mode": "kaputt"}, "Abrechnungsart"),
                             ({"machine_type_id": 999, "cost_per_sheet": "1"}, "Maschinentyp"),
                             ({"billing_mode": "time", "power_w": "-5"}, "negativ"),
                             ({"billing_mode": "time", "lifespan_hours": "0"}, "größer als 0")]:
        r = client.post("/api/machines", data={**base, **override})
        assert r.status_code == 400 and needle in r.json()["error"], (override, r.text)

    product_id, ids = create_recipe_product(client, db)
    r = client.post(f"/machines/{ids['printer']}/delete")
    assert "error=" in r.headers["location"]
    assert client.post(f"/machines/{machine.id}/delete").headers["location"] == "/machines"


def test_machine_type_api(client, db):
    r = client.post("/api/machine-types/quick-add", data={"name": "Stickmaschine", "default_billing_mode": "sheet"})
    assert r.status_code == 200
    body = r.json()
    assert any(t["name"] == "Stickmaschine" and t["default_billing_mode"] == "sheet" for t in body["machine_types"])
    # Doppelt anlegen erzeugt keinen zweiten Eintrag
    again = client.post("/api/machine-types/quick-add", data={"name": "Stickmaschine"}).json()
    assert [t["name"] for t in again["machine_types"]].count("Stickmaschine") == 1
    assert client.post("/api/machine-types/quick-add", data={"name": " "}).status_code == 400
    assert client.post("/api/machine-types/quick-add", data={"name": "X", "default_billing_mode": "zzz"}).status_code == 400


# --------------------------------------------------------------------------- Produkte

def test_product_lifecycle(client, db):
    product_id, ids = create_recipe_product(client, db)

    detail = client.get(f"/products/{product_id}")
    assert detail.status_code == 200
    assert "Sticker-Bogen" in detail.text and "Plotter" in detail.text and "Drucker" in detail.text
    # Charge: 0,80 + 1,50 + 0,28 + 0,60 + 4,00 = 7,18 ; /4 = 1,79 ; + 0,10 Verpackung = 1,89
    api = client.get(f"/api/products/{product_id}/details").json()
    assert api["total_cost"] == 1.89
    assert api["product_type"] == "3D-Drucker + Schneideplotter"  # Reihenfolge der Maschinenzeilen

    assert client.get(f"/products/{product_id}/edit").status_code == 200
    r = client.post(f"/products/{product_id}/update", data=product_form(
        batch_yield="2", is_for_market=None, selling_price="5",
        used_packaging_id=[str(ids["beutel"])], used_packaging_amount=["1"],
        used_material_id=[str(ids["pla"])], used_material_amount=["40"],
        used_machine_id=[str(ids["printer"])], used_machine_value=["120"],
    ))
    assert r.status_code == 303
    # Charge: 0,80 + 0,28 + 4,00 = 5,08 ; /2 = 2,54 ; + 0,10 = 2,64
    api = client.get(f"/api/products/{product_id}/details").json()
    assert api["total_cost"] == 2.64
    detail = client.get(f"/products/{product_id}").text
    assert "Sticker-Bogen" not in detail and "Manuell festgelegt" in detail and "Nur Kalkulation" in detail

    for query in ["", "?search=Test", "?market_filter=market", "?market_filter=non_market", "?sort_by=type",
                  "?sort_by=purchase_price&sort_order=desc", "?sort_by=selling_price", "?sort_by=updated_at"]:
        assert client.get("/products" + query).status_code == 200, query
    assert client.get("/api/products/search?q=Test").json()[0]["name"] == "Testprodukt"

    r = client.post(f"/products/{product_id}/toggle-market")
    assert r.status_code == 303
    r = client.post("/products/bulk-toggle-market", data={"product_ids": str(product_id), "is_for_market": "1"})
    assert r.status_code == 303

    assert client.post(f"/products/{product_id}/delete").headers["location"].startswith("/products")
    assert client.get(f"/products/{product_id}").status_code == 404


def test_product_form_validation(client, db):
    pla = add_material(client, db)
    bad = [
        ({"name": "  "}, "Produktnamen"),
        ({"batch_yield": "0"}, "Ausbeute"),
        ({"used_labor_minutes": ["-5"]}, "negativ"),
        ({"used_labor_minutes": ["abc"]}, "Ungültige Zahl"),
        ({"used_packaging_id": ["999"], "used_packaging_amount": ["1"]}, "nicht gefunden"),
        ({"used_material_id": ["999"], "used_material_amount": ["5"]}, "nicht gefunden"),
        ({"used_material_id": ["x"], "used_material_amount": ["5"]}, "Ungültige"),
    ]
    for override, needle in bad:
        r = client.post("/products", data=product_form(**override))
        assert r.status_code == 400 and needle in r.text, (override, r.status_code, r.text)
    # Leere/0-Zeilen werden ignoriert
    r = client.post("/products", data=product_form(used_material_id=[str(pla), ""], used_material_amount=["0", ""]))
    assert r.status_code == 303


def test_labor_steps_and_packaging_roundtrip_through_the_form(client, db):
    beutel = add_material(client, db, "Beutel", "piece", "0.10", "other")
    karte = add_material(client, db, "Karte", "piece", "0.05", "other")
    r = client.post("/products", data=product_form(
        batch_yield="2",
        used_labor_description=["Entgraten", "", "Montage"], used_labor_minutes=["30", "0", "15"], used_labor_rate=["20", "20", "40"],
        used_packaging_id=[str(beutel), str(karte)], used_packaging_amount=["1", "2"],
    ))
    assert r.status_code == 303
    product_id = int(re.match(r"/products/(\d+)", r.headers["location"]).group(1))

    product = db.get(Product, product_id)
    assert [(s.description, float(s.minutes), float(s.hourly_rate)) for s in product.labor_steps] == [
        ("Entgraten", 30.0, 20.0), ("Montage", 15.0, 40.0)]        # Zeile mit 0 Minuten wird ignoriert
    assert product.labor_minutes == 45
    assert [(l.material.name, float(l.amount)) for l in product.packaging_links] == [("Beutel", 1.0), ("Karte", 2.0)]

    # Charge: 30/60*20 + 15/60*40 = 20 ; /2 = 10 ; Verpackung 0,10 + 2*0,05 = 0,20 ; EK 10,20
    assert client.get(f"/api/products/{product_id}/details").json()["total_cost"] == 10.2
    detail = client.get(f"/products/{product_id}").text
    assert "Entgraten" in detail and "Montage" in detail and "Beutel" in detail and "Karte" in detail

    edit = client.get(f"/products/{product_id}/edit").text
    assert "Entgraten" in edit and "Montage" in edit                # Startwerte für die Zeilenlisten

    # Verpackungsmaterial ist geschützt, solange ein Produkt es verwendet
    assert "error=" in client.post(f"/materials/{beutel}/delete").headers["location"]

    # Bearbeiten ersetzt beide Listen vollständig
    r = client.post(f"/products/{product_id}/update", data=product_form(
        used_labor_description=["Nur ein Schritt"], used_labor_minutes=["6"], used_labor_rate=["10"],
    ))
    assert r.status_code == 303
    db.expire_all()
    product = db.get(Product, product_id)
    assert [s.description for s in product.labor_steps] == ["Nur ein Schritt"] and product.packaging_links == []


def test_deleting_a_product_keeps_event_items(client, db):
    product_id, ids = create_recipe_product(client, db)
    r = client.post("/events/new", data={"name": "Markt"})
    event_id = int(r.headers["location"].split("/")[-1])
    client.post(f"/events/{event_id}/items/add", data={"product_id": product_id, "target_quantity": "3"})
    assert client.post(f"/products/{product_id}/delete").status_code == 303
    assert client.get(f"/events/{event_id}").status_code == 200


def recipe_payload(ids, **overrides):
    payload = {
        "yield_qty": 4, "selling_price": None,
        "labor": [{"key": "l1", "description": "Montage", "minutes": 10, "hourly_rate": 24}],
        "packaging": [{"key": "p1", "material_id": ids["beutel"], "amount": 1}],
        "materials": [{"key": "m1", "material_id": ids["pla"], "amount": 40},
                      {"key": "m2", "material_id": ids["bogen"], "amount": 3}],
        "machines": [{"key": "a1", "machine_id": ids["printer"], "value": 120},
                     {"key": "a2", "machine_id": ids["plotter"], "value": 5}],
    }
    payload.update(overrides)
    return payload


def test_live_preview_matches_the_saved_product(client, db):
    """Die Vorschau im Formular (/api/calculate) und die Detailseite dürfen nie abweichen."""
    product_id, ids = create_recipe_product(client, db)
    saved = db.get(Product, product_id).calculate_costs()

    preview = client.post("/api/calculate", json=recipe_payload(ids))
    assert preview.status_code == 200, preview.text
    preview = preview.json()

    for key in ("batch_material_cost", "batch_machine_cost", "batch_labor_cost", "batch_total_cost", "material_cost",
                "machine_cost", "labor_cost", "production_cost", "packaging_cost", "total_cost",
                "recommended_selling_price", "selling_price", "profit", "margin_percent", "yield_qty"):
        assert preview[key] == saved[key], key
    assert [l["cost"] for l in preview["materials"]] == [l["cost"] for l in saved["materials"]]
    assert [l["cost"] for l in preview["machines"]] == [l["cost"] for l in saved["machines"]]
    assert [l["cost"] for l in preview["labor"]] == [l["cost"] for l in saved["labor"]]
    assert [l["cost"] for l in preview["packaging"]] == [l["cost"] for l in saved["packaging"]]
    assert preview["total_cost"] == 1.89
    assert preview["type_label"] == "3D-Drucker + Schneideplotter"
    # Zeilenschlüssel des Formulars kommen unverändert zurück
    assert [l["key"] for l in preview["materials"]] == ["m1", "m2"]
    assert [l["key"] for l in preview["machines"]] == ["a1", "a2"]
    assert [l["key"] for l in preview["labor"]] == ["l1"] and [l["key"] for l in preview["packaging"]] == ["p1"]


def test_live_preview_custom_price_empty_form_and_errors(client, db):
    product_id, ids = create_recipe_product(client, db)

    custom = client.post("/api/calculate", json=recipe_payload(ids, selling_price=5)).json()
    assert custom["has_custom_selling_price"] is True and custom["selling_price"] == 5.0
    assert custom["profit"] == 3.11                       # 5,00 - 1,894

    empty = client.post("/api/calculate", json={}).json()
    assert empty["total_cost"] == 0 and empty["materials"] == [] and empty["type_label"] == "Handarbeit"

    cheaper = client.post("/api/calculate", json=recipe_payload(ids, yield_qty=8)).json()
    assert cheaper["production_cost"] < 1.79

    assert client.post("/api/calculate", json=recipe_payload(ids, yield_qty=0)).status_code == 422
    negative = recipe_payload(ids, packaging=[{"material_id": ids["beutel"], "amount": -1}])
    assert client.post("/api/calculate", json=negative).status_code == 422
    negative = recipe_payload(ids, labor=[{"minutes": 5, "hourly_rate": -20}])
    assert client.post("/api/calculate", json=negative).status_code == 422
    unknown = client.post("/api/calculate", json=recipe_payload(ids, materials=[{"material_id": 999, "amount": 5}]))
    assert unknown.status_code == 400 and "Material" in unknown.json()["detail"]
    unknown = client.post("/api/calculate", json=recipe_payload(ids, machines=[{"machine_id": 999, "value": 5}]))
    assert unknown.status_code == 400 and "Maschine" in unknown.json()["detail"]


def test_machine_rate_api(client):
    rate = client.get("/api/machine-rate", params={"depreciation_euro": "350", "lifespan_hours": "3000", "power_w": "100"}).json()
    assert round(rate["cost_per_hour"], 4) == 0.1387
    assert round(rate["power_cost"], 3) == 0.022 and round(rate["depreciation_cost"], 3) == 0.117
    assert round(rate["sheet_min_cost"], 4) == 0.0758          # 2,5 min + 0,07 € Verschleiß (Standardwerte)
    assert rate["recommended_sheet_price"] == 0.08

    custom = client.get("/api/machine-rate", params={"depreciation_euro": "600", "lifespan_hours": "1000", "power_w": "0",
                                                     "minutes_per_sheet": "10", "wear_cost": "0.05"}).json()
    assert custom["cost_per_hour"] == 0.6 and round(custom["sheet_machine_cost"], 4) == 0.1
    assert custom["recommended_sheet_price"] == 0.15

    bad = client.get("/api/machine-rate", params={"power_w": "-1"})
    assert bad.status_code == 400 and "negativ" in bad.json()["error"]


def test_live_preview_uses_the_configured_electricity_price(client, db):
    printer = add_machine(client, db, "Heizer", depreciation_euro="0", lifespan_hours="1", power_w="1000")
    payload = {"machines": [{"machine_id": printer, "value": 60}]}
    assert client.post("/api/calculate", json=payload).json()["batch_machine_cost"] == 0.22
    client.post("/settings", data={"electricity_price_kwh": "0,40", "labor_rate_per_hour": "20", "margin_multiplier": "2"})
    assert client.post("/api/calculate", json=payload).json()["batch_machine_cost"] == 0.4
    assert client.get("/api/machine-rate", params={"power_w": "1000", "lifespan_hours": "1"}).json()["cost_per_hour"] == 0.4


# --------------------------------------------------------------------------- Events

def test_event_lifecycle_and_material_needs(client, db):
    product_id, ids = create_recipe_product(client, db)  # Ausbeute 4
    r = client.post("/events/new", data={"name": "Sommermarkt", "event_date": "2026-10-01", "load_default_packlist": "on"})
    assert r.status_code == 303
    event_id = int(r.headers["location"].split("/")[-1])

    client.post(f"/events/{event_id}/items/add", data={"product_id": product_id, "target_quantity": "6", "custom_vk": "5,50"})
    client.post(f"/events/{event_id}/items/add", data={"product_id": product_id, "target_quantity": "2"})  # addiert auf 8
    page = client.get(f"/events/{event_id}")
    assert page.status_code == 200
    # 8 Stück / Ausbeute 4 = 2 Chargen -> 80 g PLA, 6 Bögen
    assert "PLA: <strong>80.0 g" in page.text and "Sticker-Bogen: <strong>6.0 Bögen" in page.text

    item_id = int(re.search(r"/items/(\d+)/adjust", page.text).group(1))
    assert client.post(f"/events/{event_id}/items/{item_id}/adjust", data={"delta": "1"}).status_code == 303
    assert client.post(f"/events/{event_id}/items/{item_id}/update-vk", data={"custom_vk": "6"}).status_code == 303

    assert client.get(f"/events/{event_id}/print").status_code == 200
    assert client.get(f"/events/{event_id}/edit").status_code == 200
    assert client.get("/events?status_filter=active&sort_by=name").status_code == 200
    assert client.post(f"/events/{event_id}/update", data={"name": "Herbstmarkt", "status": "ready"}).status_code == 303
    assert client.post(f"/events/{event_id}/status", data={"status": "completed"}).status_code == 303
    assert client.post(f"/events/{event_id}/ideas", data={"product_ideas": "Mehr Sticker"}).status_code == 303

    assert client.post(f"/events/{event_id}/todos/add", data={"title": "Wechselgeld", "category": "Kasse"}).status_code == 303
    todo_id = int(re.search(r"/todos/(\d+)/toggle", client.get(f"/events/{event_id}").text).group(1))
    assert client.post(f"/events/{event_id}/todos/{todo_id}/toggle").status_code == 303
    assert client.post(f"/events/{event_id}/todos/load-template").status_code == 303
    assert client.post(f"/events/{event_id}/todos/bulk-toggle", data={"is_done": "1"}).status_code == 303
    assert client.post(f"/events/{event_id}/todos/{todo_id}/delete").status_code == 303

    assert client.post(f"/events/{event_id}/items/{item_id}/delete").status_code == 303
    assert client.post(f"/events/{event_id}/delete").headers["location"] == "/events"


# --------------------------------------------------------------------------- Feedback, Einstellungen, Tools, Dashboard

def test_feedback_lifecycle(client):
    assert client.post("/feedback-ideas", data={"description": "Mehr Farben"}).status_code == 303
    page = client.get("/feedback-ideas").text
    assert "Mehr Farben" in page
    item_id = int(re.search(r"/feedback-ideas/(\d+)/", page).group(1))
    assert client.get(f"/feedback-ideas/{item_id}/edit").status_code == 200
    assert client.post(f"/feedback-ideas/{item_id}/update", data={"description": "Noch mehr Farben"}).status_code == 303
    assert client.post(f"/feedback-ideas/{item_id}/status").status_code == 303
    assert client.get("/feedback-ideas?status_filter=done").status_code == 200
    assert client.post(f"/feedback-ideas/{item_id}/delete").status_code == 303


def test_settings_sync_categories_and_machine_types(client, db):
    product_id, ids = create_recipe_product(client, db)  # Kategorie 'Sonstiges' wird verwendet
    r = client.post("/settings", data={
        "electricity_price_kwh": "0,30", "labor_rate_per_hour": "22", "margin_multiplier": "2,5",
        "company_name": "Shop",
        "product_categories": "Dekoration\nNeu",
        "machine_types": "3D-Drucker\nSchneideplotter | Bogen\nStickmaschine | Bogen",
    })
    assert r.status_code == 303
    page = client.get("/settings").text
    categories = re.search(r'<textarea id="product_categories"[^>]*>(.*?)</textarea>', page, re.S).group(1)
    machine_types = re.search(r'<textarea id="machine_types"[^>]*>(.*?)</textarea>', page, re.S).group(1)
    assert "Neu" in categories and "Stickmaschine | Bogen" in machine_types
    assert "Sonstiges" in categories                    # in Verwendung -> bleibt trotz Streichung
    assert "Technik" not in categories                  # ungenutzt -> entfernt
    assert "Tintenstrahl-Drucker" not in machine_types
    assert "3D-Drucker" in machine_types                # von einer Maschine verwendet
    assert client.get("/machines/new").status_code == 200
    # Strompreis 0,30 statt 0,22 wirkt in der Kalkulation: EK 1,894 -> 1,898 €
    assert client.get(f"/api/products/{product_id}/details").json()["total_cost"] == 1.90


def test_dashboard_with_data(client, db):
    create_recipe_product(client, db)
    page = client.get("/")
    assert page.status_code == 200 and "Testprodukt" in page.text


def test_svg_converter_roundtrip(client):
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), (200, 30, 30)).save(buffer, format="PNG")
    r = client.post("/tools/png-to-svg", data={"save_file": "true", "description": "Rot"},
                    files={"image": ("rot.png", buffer.getvalue(), "image/png")})
    assert r.status_code == 200, r.text[:300]
    assert client.get("/tools/converted-files").status_code == 200
    page = client.get("/tools/converted-files").text
    match = re.search(r"/tools/converted-files/(\d+)/preview", page)
    assert match, "Konvertierte Datei fehlt in der Bibliothek"
    file_id = match.group(1)
    assert client.get(f"/tools/converted-files/{file_id}/preview").status_code == 200
    assert client.get(f"/tools/converted-files/{file_id}/download/svg").status_code == 200
    assert client.get(f"/tools/converted-files/{file_id}/download/png").status_code == 200
    assert client.post(f"/tools/converted-files/{file_id}/delete").status_code == 303

    bad = client.post("/tools/png-to-svg", files={"image": ("x.txt", b"nope", "text/plain")})
    assert bad.status_code == 200 and "erlaubt" in bad.text
