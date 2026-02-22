from fastapi import FastAPI, Request, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from database import engine, get_db, SessionLocal
from models import Base, Product, Material, MaterialType, Machine, Feedback, Idea, ConvertedFile, ProductImage, ProductComponent, SalesOrder, SalesOrderItem, STROM_PREIS_KWH
from datetime import datetime
import time
import os
import uuid
import vtracer
from pathlib import Path


def parse_decimal(value: str) -> float:
    """Konvertiert einen String mit Komma oder Punkt als Dezimaltrenner zu float"""
    if value is None:
        return 0.0
    # Ersetze Komma durch Punkt für die Konvertierung
    return float(str(value).replace(',', '.'))


def minutes_to_hours(minutes: float) -> float:
    """Konvertiert Minuten in Stunden"""
    return minutes / 60.0


def seed_material_types(db: Session):
    """Initialisiert Standard-Materialtypen falls noch keine existieren"""
    existing = db.query(MaterialType).first()
    if existing:
        return  # Bereits initialisiert
    
    default_types = [
        ("filament", "3D-Filament (€/kg)", "Filament für 3D-Drucker", 1),
        ("sticker_sheet", "Sticker-Sheet (€/Bogen)", "Bögen für Sticker", 2),
        ("diecut_sticker", "DieCut-Sticker Material", "Material für einzelne Sticker", 3),
        ("paper", "Papier", "Verschiedene Papiersorten", 4),
        ("laser_material", "Laser-Material (€/Stück)", "Material für Laser-Gravur", 5),
        ("other", "Sonstiges", "Andere Materialien", 99),
    ]
    
    for key, name, desc, sort_order in default_types:
        mt = MaterialType(key=key, name=name, description=desc, sort_order=sort_order)
        db.add(mt)
    
    db.commit()
    print("Standard-Materialtypen wurden initialisiert.")


# Wait for database and create tables
max_retries = 30
retry_delay = 2

for i in range(max_retries):
    try:
        Base.metadata.create_all(bind=engine)
        print("Database connected and tables created successfully!")
        # Initialisiere Standard-Materialtypen
        db = SessionLocal()
        try:
            seed_material_types(db)
        finally:
            db.close()
        break
    except OperationalError as e:
        print(f"Database not ready yet (attempt {i+1}/{max_retries}). Retrying in {retry_delay} seconds...")
        time.sleep(retry_delay)
else:
    print("Could not connect to database after maximum retries!")
    raise Exception("Database connection failed")

app = FastAPI(title="Picobellu Kalkulator")

# Templates
templates = Jinja2Templates(directory="templates")

# Categories
CATEGORIES = [
    "Dekoration",
    "Technik", 
    "Ersatzteile",
    "Spielzeug",
    "Werkzeuge",
    "Sticker",
    "Papierprodukte",
    "Sonstiges"
]

# Materialtypen werden jetzt aus der DB geladen
def get_material_types(db: Session, only_active: bool = True):
    """Lädt Materialtypen aus der Datenbank"""
    query = db.query(MaterialType)
    if only_active:
        query = query.filter(MaterialType.is_active == 1)
    return query.order_by(MaterialType.sort_order, MaterialType.name).all()

# Produkttypen
PRODUCT_TYPES = [
    ("3d_print", "3D-Druck"),
    ("sticker_sheet", "Sticker-Sheet"),
    ("diecut_sticker", "DieCut-Sticker"),
    ("paper", "Papierprodukt"),
    ("stationery", "Schreibwaren"),
    ("assembly", "Zusammenbau-Produkt"),
]

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard mit Übersicht"""
    products = db.query(Product).order_by(Product.updated_at.desc()).limit(5).all()
    total_products = db.query(Product).count()
    total_materials = db.query(Material).count()
    total_machines = db.query(Machine).count()
    
    # Berechne Durchschnittskosten
    all_products = db.query(Product).all()
    avg_cost = 0
    if all_products:
        total = sum([p.calculate_costs()['total_cost'] for p in all_products])
        avg_cost = total / len(all_products)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "products": products,
        "total_products": total_products,
        "total_materials": total_materials,
        "total_machines": total_machines,
        "avg_cost": round(avg_cost, 2),
        "categories": CATEGORIES
    })

# ===== MATERIAL ROUTES =====

@app.get("/materials", response_class=HTMLResponse)
async def list_materials(request: Request, material_type: str = "", db: Session = Depends(get_db)):
    """Liste aller Materialien"""
    query = db.query(Material)
    
    if material_type:
        query = query.filter(Material.material_type == material_type)
    
    materials = query.order_by(Material.material_type, Material.name).all()
    material_types = get_material_types(db)
    
    return templates.TemplateResponse("materials/list.html", {
        "request": request,
        "materials": materials,
        "material_type": material_type,
        "material_types": material_types
    })

@app.get("/materials/new", response_class=HTMLResponse)
async def new_material_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neues Material"""
    material_types = get_material_types(db)
    return templates.TemplateResponse("materials/form.html", {
        "request": request,
        "material": None,
        "material_types": material_types,
        "title": "Neues Material"
    })

@app.post("/materials")
async def create_material(
    request: Request,
    name: str = Form(...),
    material_type: str = Form(...),
    brand: str = Form(""),
    color: str = Form(""),
    unit: str = Form(...),
    price_per_unit: float = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neues Material erstellen"""
    material = Material(
        name=name,
        material_type=material_type,
        brand=brand,
        color=color,
        unit=unit,
        price_per_unit=price_per_unit,
        description=description
    )
    
    db.add(material)
    db.commit()
    db.refresh(material)
    
    return RedirectResponse(url="/materials", status_code=303)

@app.get("/materials/{material_id}/edit", response_class=HTMLResponse)
async def edit_material_form(material_id: int, request: Request, db: Session = Depends(get_db)):
    """Formular zum Bearbeiten eines Materials"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")
    
    material_types = get_material_types(db)
    return templates.TemplateResponse("materials/form.html", {
        "request": request,
        "material": material,
        "material_types": material_types,
        "title": "Material bearbeiten"
    })

@app.post("/materials/{material_id}/update")
async def update_material(
    material_id: int,
    request: Request,
    name: str = Form(...),
    material_type: str = Form(...),
    brand: str = Form(""),
    color: str = Form(""),
    unit: str = Form(...),
    price_per_unit: float = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Material aktualisieren"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")
    
    material.name = name
    material.material_type = material_type
    material.brand = brand
    material.color = color
    material.unit = unit
    material.price_per_unit = price_per_unit
    material.description = description
    material.updated_at = datetime.utcnow()
    
    db.commit()
    
    return RedirectResponse(url="/materials", status_code=303)

@app.post("/materials/{material_id}/delete")
async def delete_material(material_id: int, db: Session = Depends(get_db)):
    """Material löschen"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")
    
    db.delete(material)
    db.commit()
    
    return RedirectResponse(url="/materials", status_code=303)

# ===== MATERIALTYPEN ROUTES =====

@app.get("/material-types", response_class=HTMLResponse)
async def list_material_types(request: Request, db: Session = Depends(get_db)):
    """Liste aller Materialtypen (Verwaltung)"""
    material_types = db.query(MaterialType).order_by(MaterialType.sort_order, MaterialType.name).all()
    
    return templates.TemplateResponse("materials/type_list.html", {
        "request": request,
        "material_types": material_types,
        "title": "Materialtypen verwalten"
    })

@app.get("/material-types/new", response_class=HTMLResponse)
async def new_material_type_form(request: Request):
    """Formular für neuen Materialtyp"""
    return templates.TemplateResponse("materials/type_form.html", {
        "request": request,
        "material_type": None,
        "title": "Neuer Materialtyp"
    })

@app.post("/material-types")
async def create_material_type(
    request: Request,
    key: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    sort_order: int = Form(0),
    db: Session = Depends(get_db)
):
    """Neuen Materialtyp erstellen"""
    # Prüfe ob Key bereits existiert
    existing = db.query(MaterialType).filter(MaterialType.key == key).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Materialtyp mit Schlüssel '{key}' existiert bereits")
    
    material_type = MaterialType(
        key=key,
        name=name,
        description=description,
        sort_order=sort_order,
        is_active=1
    )
    
    db.add(material_type)
    db.commit()
    db.refresh(material_type)
    
    return RedirectResponse(url="/material-types", status_code=303)

@app.get("/material-types/{type_id}/edit", response_class=HTMLResponse)
async def edit_material_type_form(type_id: int, request: Request, db: Session = Depends(get_db)):
    """Formular zum Bearbeiten eines Materialtyps"""
    material_type = db.query(MaterialType).filter(MaterialType.id == type_id).first()
    if not material_type:
        raise HTTPException(status_code=404, detail="Materialtyp nicht gefunden")
    
    return templates.TemplateResponse("materials/type_form.html", {
        "request": request,
        "material_type": material_type,
        "title": "Materialtyp bearbeiten"
    })

@app.post("/material-types/{type_id}/update")
async def update_material_type(
    type_id: int,
    request: Request,
    key: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    sort_order: int = Form(0),
    is_active: int = Form(1),
    db: Session = Depends(get_db)
):
    """Materialtyp aktualisieren"""
    material_type = db.query(MaterialType).filter(MaterialType.id == type_id).first()
    if not material_type:
        raise HTTPException(status_code=404, detail="Materialtyp nicht gefunden")
    
    # Prüfe ob Key bereits von anderem Typ verwendet wird
    existing = db.query(MaterialType).filter(MaterialType.key == key, MaterialType.id != type_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Materialtyp mit Schlüssel '{key}' existiert bereits")
    
    material_type.key = key
    material_type.name = name
    material_type.description = description
    material_type.sort_order = sort_order
    material_type.is_active = is_active
    material_type.updated_at = datetime.utcnow()
    
    db.commit()
    
    return RedirectResponse(url="/material-types", status_code=303)

@app.post("/material-types/{type_id}/delete")
async def delete_material_type(type_id: int, db: Session = Depends(get_db)):
    """Materialtyp löschen (nur wenn nicht in Verwendung)"""
    material_type = db.query(MaterialType).filter(MaterialType.id == type_id).first()
    if not material_type:
        raise HTTPException(status_code=404, detail="Materialtyp nicht gefunden")
    
    # Prüfe ob Materialien diesen Typ verwenden
    materials_using_type = db.query(Material).filter(Material.material_type == material_type.key).count()
    if materials_using_type > 0:
        raise HTTPException(status_code=400, detail=f"Materialtyp wird von {materials_using_type} Materialien verwendet und kann nicht gelöscht werden")
    
    db.delete(material_type)
    db.commit()
    
    return RedirectResponse(url="/material-types", status_code=303)

# ===== MACHINE ROUTES =====

@app.get("/machines", response_class=HTMLResponse)
async def list_machines(request: Request, machine_type: str = "", db: Session = Depends(get_db)):
    """Liste aller Maschinen"""
    query = db.query(Machine)
    
    if machine_type:
        query = query.filter(Machine.machine_type == machine_type)
    
    machines = query.order_by(Machine.machine_type, Machine.name).all()
    
    return templates.TemplateResponse("machines/list.html", {
        "request": request,
        "machines": machines,
        "machine_type": machine_type,
        "machine_types": [("3d_printer", "3D-Drucker"), ("cutter_plotter", "Cutter/Plotter"), ("inkjet_printer", "Tintenstrahl-Drucker"), ("other", "Sonstiges")]
    })

@app.get("/machines/new", response_class=HTMLResponse)
async def new_machine_form(request: Request):
    """Formular für neue Maschine"""
    return templates.TemplateResponse("machines/form.html", {
        "request": request,
        "machine": None,
        "machine_types": [("3d_printer", "3D-Drucker"), ("cutter_plotter", "Cutter/Plotter"), ("inkjet_printer", "Tintenstrahl-Drucker"), ("other", "Sonstiges")],
        "title": "Neue Maschine",
        "STROM_PREIS_KWH": STROM_PREIS_KWH
    })

@app.post("/machines")
async def create_machine(
    request: Request,
    name: str = Form(...),
    machine_type: str = Form(...),
    depreciation_euro: str = Form("0"),
    lifespan_hours: str = Form("1"),
    power_kw: str = Form("0"),
    lifespan_pages: str = Form(""),
    depreciation_per_page: str = Form(""),
    cost_per_sheet: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neue Maschine erstellen"""
    machine = Machine(
        name=name,
        machine_type=machine_type,
        depreciation_euro=parse_decimal(depreciation_euro),
        lifespan_hours=parse_decimal(lifespan_hours),
        power_kw=parse_decimal(power_kw),
        lifespan_pages=parse_decimal(lifespan_pages) if lifespan_pages else None,
        depreciation_per_page=parse_decimal(depreciation_per_page) if depreciation_per_page else None,
        cost_per_sheet=parse_decimal(cost_per_sheet) if cost_per_sheet else None,
        description=description
    )
    
    db.add(machine)
    db.commit()
    db.refresh(machine)
    
    return RedirectResponse(url="/machines", status_code=303)

@app.get("/machines/{machine_id}/edit", response_class=HTMLResponse)
async def edit_machine_form(machine_id: int, request: Request, db: Session = Depends(get_db)):
    """Formular zum Bearbeiten einer Maschine"""
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")
    
    return templates.TemplateResponse("machines/form.html", {
        "request": request,
        "machine": machine,
        "machine_types": [("3d_printer", "3D-Drucker"), ("cutter_plotter", "Cutter/Plotter"), ("inkjet_printer", "Tintenstrahl-Drucker"), ("other", "Sonstiges")],
        "title": "Maschine bearbeiten",
        "STROM_PREIS_KWH": STROM_PREIS_KWH
    })

@app.post("/machines/{machine_id}/update")
async def update_machine(
    machine_id: int,
    request: Request,
    name: str = Form(...),
    machine_type: str = Form(...),
    depreciation_euro: str = Form("0"),
    lifespan_hours: str = Form("1"),
    power_kw: str = Form("0"),
    lifespan_pages: str = Form(""),
    depreciation_per_page: str = Form(""),
    cost_per_sheet: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Maschine aktualisieren"""
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")
    
    machine.name = name
    machine.machine_type = machine_type
    machine.depreciation_euro = parse_decimal(depreciation_euro)
    machine.lifespan_hours = parse_decimal(lifespan_hours)
    machine.power_kw = parse_decimal(power_kw)
    machine.lifespan_pages = parse_decimal(lifespan_pages) if lifespan_pages else None
    machine.depreciation_per_page = parse_decimal(depreciation_per_page) if depreciation_per_page else None
    machine.cost_per_sheet = parse_decimal(cost_per_sheet) if cost_per_sheet else None
    machine.description = description
    machine.updated_at = datetime.utcnow()
    
    db.commit()
    
    return RedirectResponse(url="/machines", status_code=303)

@app.post("/machines/{machine_id}/delete")
async def delete_machine(machine_id: int, db: Session = Depends(get_db)):
    """Maschine löschen"""
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")
    
    db.delete(machine)
    db.commit()
    
    return RedirectResponse(url="/machines", status_code=303)

# ===== PRODUCT ROUTES - Übersicht =====

@app.get("/products", response_class=HTMLResponse)
async def list_products(
    request: Request, 
    search: str = "",
    category: str = "",
    db: Session = Depends(get_db)
):
    """Produktliste mit Filter"""
    from sqlalchemy.orm import joinedload
    
    query = db.query(Product).options(joinedload(Product.images))
    
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    
    if category:
        query = query.filter(Product.category == category)
    
    products = query.order_by(Product.name).all()
    
    # Füge Berechnungen hinzu
    products_with_calc = []
    for p in products:
        calc = p.calculate_costs()
        products_with_calc.append({
            'product': p,
            'calc': calc
        })
    
    return templates.TemplateResponse("products/list.html", {
        "request": request,
        "products": products_with_calc,
        "search": search,
        "category": category,
        "categories": CATEGORIES
    })

# ===== NEUES PRODUKT - TYP AUSWAHL =====

@app.get("/products/new", response_class=HTMLResponse)
async def new_product_select_type(request: Request):
    """Auswahlseite für Produkttyp beim Erstellen eines neuen Produkts"""
    return templates.TemplateResponse("products/product_type_select.html", {
        "request": request,
        "title": "Neues Produkt"
    })

# ===== 3D-DRUCK PRODUKTE =====

@app.get("/products/3d-print/new", response_class=HTMLResponse)
async def new_3d_print_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neues 3D-Druck Produkt"""
    filaments = db.query(Material).filter(Material.material_type == "filament").order_by(Material.name).all()
    machines = db.query(Machine).filter(Machine.machine_type == "3d_printer").order_by(Machine.name).all()
    
    return templates.TemplateResponse("products/form_3d_print.html", {
        "request": request,
        "product": None,
        "categories": CATEGORIES,
        "filaments": filaments,
        "machines": machines,
        "title": "Neuer 3D-Druck"
    })

@app.post("/products/3d-print")
async def create_3d_print(
    request: Request,
    name: str = Form(...),
    category: str = Form("Sonstiges"),
    filament_material_id: int = Form(...),
    filament_weight_g: str = Form(...),
    print_time_hours: str = Form("0"),
    machine_id: int = Form(...),
    labor_minutes: str = Form("0"),
    labor_rate_per_hour: str = Form("20.00"),
    packaging_cost: str = Form("0"),
    shipping_cost: str = Form("0"),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neues 3D-Druck Produkt erstellen"""
    # Konvertiere Komma zu Punkt und berechne Stunden aus Minuten
    product = Product(
        name=name,
        product_type="3d_print",
        category=category,
        filament_material_id=filament_material_id,
        filament_weight_g=parse_decimal(filament_weight_g),
        print_time_hours=parse_decimal(print_time_hours),
        machine_id=machine_id,
        labor_minutes=parse_decimal(labor_minutes),
        labor_rate_per_hour=parse_decimal(labor_rate_per_hour),
        packaging_cost=parse_decimal(packaging_cost),
        shipping_cost=parse_decimal(shipping_cost),
        notes=notes
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return RedirectResponse(url=f"/products/{product.id}", status_code=303)

# ===== STICKER-BOGEN PRODUKTE =====

@app.get("/products/sticker-sheet/new", response_class=HTMLResponse)
async def new_sticker_sheet_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neues Sticker-Sheet Produkt"""
    sticker_sheets = db.query(Material).filter(Material.material_type == "sticker_sheet").order_by(Material.name).all()
    # Lade alle Maschinen
    machines = db.query(Machine).order_by(Machine.name).all()
    
    return templates.TemplateResponse("products/form_sticker_sheet.html", {
        "request": request,
        "product": None,
        "categories": CATEGORIES,
        "sticker_sheets": sticker_sheets,
        "machines": machines,
        "title": "Neues Sticker-Sheet"
    })

@app.post("/products/sticker-sheet")
async def create_sticker_sheet(
    request: Request,
    name: str = Form(...),
    category: str = Form("Sonstiges"),
    sheet_material_id: int = Form(...),
    units_per_sheet: str = Form("3"),
    units_per_batch: str = Form("3"),
    calculation_mode: str = Form("per_unit"),
    machine_ids: list[int] = Form([]),  # Mehrere Maschinen
    labor_minutes: str = Form("0"),
    labor_rate_per_hour: str = Form("20.00"),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neues Sticker-Sheet Produkt erstellen"""
    # Erste Maschine als Hauptmaschine, restliche als kommaseparierte IDs
    primary_machine_id = machine_ids[0] if machine_ids else None
    additional_ids = ",".join(str(mid) for mid in machine_ids[1:]) if len(machine_ids) > 1 else None
    
    product = Product(
        name=name,
        product_type="sticker_sheet",
        category=category,
        sheet_material_id=sheet_material_id,
        sheet_count=1,  # Immer 1
        units_per_sheet=parse_decimal(units_per_sheet) if calculation_mode == "per_unit" else 1,
        units_per_batch=int(units_per_batch) if calculation_mode == "per_batch" else 1,
        calculation_mode=calculation_mode,
        machine_id=primary_machine_id,
        additional_machine_ids=additional_ids,
        labor_minutes=parse_decimal(labor_minutes),
        labor_rate_per_hour=parse_decimal(labor_rate_per_hour),
        packaging_cost=0,  # Wird beim Verkauf erfasst
        shipping_cost=0,   # Wird beim Verkauf erfasst
        notes=notes
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return RedirectResponse(url=f"/products/{product.id}", status_code=303)

# ===== SCHREIBWAREN ROUTES =====

@app.get("/products/stationery/new", response_class=HTMLResponse)
async def new_stationery_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neue Schreibwaren"""
    sticker_sheets = db.query(Material).filter(Material.material_type == "sticker_sheet").order_by(Material.name).all()
    machines = db.query(Machine).order_by(Machine.name).all()
    
    return templates.TemplateResponse("products/form_stationery.html", {
        "request": request,
        "product": None,
        "categories": CATEGORIES,
        "sticker_sheets": sticker_sheets,
        "machines": machines,
        "title": "Neue Schreibware"
    })

@app.post("/products/stationery")
async def create_stationery(
    request: Request,
    name: str = Form(...),
    category: str = Form("Sonstiges"),
    sheet_material_id: int = Form(...),
    units_per_sheet: str = Form("1"),
    units_per_batch: str = Form("10"),
    calculation_mode: str = Form("per_unit"),
    machine_ids: list[int] = Form([]),
    labor_minutes: str = Form("0"),
    labor_rate_per_hour: str = Form("20.00"),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neue Schreibware erstellen"""
    primary_machine_id = machine_ids[0] if machine_ids else None
    additional_ids = ",".join(str(mid) for mid in machine_ids[1:]) if len(machine_ids) > 1 else None
    
    product = Product(
        name=name,
        product_type="stationery",
        category=category,
        sheet_material_id=sheet_material_id,
        sheet_count=1,
        units_per_sheet=parse_decimal(units_per_sheet) if calculation_mode == "per_unit" else 1,
        units_per_batch=int(units_per_batch) if calculation_mode == "per_batch" else 1,
        calculation_mode=calculation_mode,
        machine_id=primary_machine_id,
        additional_machine_ids=additional_ids,
        labor_minutes=parse_decimal(labor_minutes),
        labor_rate_per_hour=parse_decimal(labor_rate_per_hour),
        packaging_cost=0,
        shipping_cost=0,
        notes=notes
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return RedirectResponse(url=f"/products/{product.id}", status_code=303)

# ===== DIECUT STICKER ROUTES =====

@app.get("/products/diecut-sticker/new", response_class=HTMLResponse)
async def new_diecut_sticker_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neue DieCut Sticker"""
    sticker_sheets = db.query(Material).filter(Material.material_type == "sticker_sheet").order_by(Material.name).all()
    machines = db.query(Machine).order_by(Machine.name).all()
    
    return templates.TemplateResponse("products/form_diecut_sticker.html", {
        "request": request,
        "product": None,
        "categories": CATEGORIES,
        "sticker_sheets": sticker_sheets,
        "machines": machines,
        "title": "Neue DieCut Sticker"
    })

@app.post("/products/diecut-sticker")
async def create_diecut_sticker(
    request: Request,
    name: str = Form(...),
    category: str = Form("Sonstiges"),
    sheet_material_id: int = Form(...),
    units_per_sheet: str = Form("6"),  # Standard: 6 Sticker pro Bogen
    calculation_mode: str = Form("per_unit"),
    units_per_batch: str = Form("6"),
    machine_ids: list[int] = Form([]),  # Mehrere Maschinen
    labor_minutes: str = Form("0"),
    labor_rate_per_hour: str = Form("20.00"),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neue DieCut Sticker erstellen"""
    # Erste Maschine als Hauptmaschine, restliche als kommaseparierte IDs
    primary_machine_id = machine_ids[0] if machine_ids else None
    additional_ids = ",".join(str(mid) for mid in machine_ids[1:]) if len(machine_ids) > 1 else None
    
    product = Product(
        name=name,
        product_type="diecut_sticker",
        category=category,
        sheet_material_id=sheet_material_id,
        sheet_count=1,  # Immer 1 Bogen
        units_per_sheet=parse_decimal(units_per_sheet) if calculation_mode == "per_unit" else 1,
        units_per_batch=int(units_per_batch) if calculation_mode == "per_batch" else 1,
        calculation_mode=calculation_mode,
        machine_id=primary_machine_id,
        additional_machine_ids=additional_ids,
        labor_minutes=parse_decimal(labor_minutes),
        labor_rate_per_hour=parse_decimal(labor_rate_per_hour),
        packaging_cost=0,  # Wird beim Verkauf erfasst
        shipping_cost=0,   # Wird beim Verkauf erfasst
        notes=notes
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return RedirectResponse(url=f"/products/{product.id}", status_code=303)

# ===== LASER-GRAVUR ROUTES =====

@app.get("/products/laser-engraving/new", response_class=HTMLResponse)
async def new_laser_engraving_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neue Laser-Gravur"""
    laser_materials = db.query(Material).filter(Material.material_type == "laser_material").order_by(Material.name).all()
    
    return templates.TemplateResponse("products/form_laser_engraving.html", {
        "request": request,
        "product": None,
        "categories": CATEGORIES,
        "laser_materials": laser_materials,
        "title": "Neue Laser-Gravur"
    })

@app.post("/products/laser-engraving")
async def create_laser_engraving(
    request: Request,
    name: str = Form(...),
    category: str = Form("Sonstiges"),
    laser_material_id: int = Form(...),
    laser_design_name: str = Form(...),
    # Layer 1
    laser1_type: str = Form(...),
    laser1_power_percent: str = Form("80.0"),
    laser1_speed_mm_s: str = Form("200"),
    laser1_passes: str = Form("1"),
    laser1_dpi: str = Form("300"),
    laser1_lines_per_cm: str = Form("60"),
    # Layer 2 (optional)
    laser2_type: str = Form(None),
    laser2_power_percent: str = Form("100.0"),
    laser2_speed_mm_s: str = Form("100"),
    laser2_passes: str = Form("1"),
    laser2_dpi: str = Form("300"),
    laser2_lines_per_cm: str = Form("60"),
    # Layer 3 (optional)
    laser3_type: str = Form(None),
    laser3_power_percent: str = Form("50.0"),
    laser3_speed_mm_s: str = Form("300"),
    laser3_passes: str = Form("1"),
    laser3_dpi: str = Form("600"),
    laser3_lines_per_cm: str = Form("120"),
    labor_minutes: str = Form("0"),
    labor_rate_per_hour: str = Form("20.00"),
    packaging_cost: str = Form("0"),
    shipping_cost: str = Form("0"),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neue Laser-Gravur erstellen"""
    product = Product(
        name=name,
        product_type="laser_engraving",
        category=category,
        laser_material_id=laser_material_id,
        laser_design_name=laser_design_name,
        # Layer 1
        laser1_type=laser1_type,
        laser1_power_percent=parse_decimal(laser1_power_percent),
        laser1_speed_mm_s=parse_decimal(laser1_speed_mm_s),
        laser1_passes=int(parse_decimal(laser1_passes)),
        laser1_dpi=int(parse_decimal(laser1_dpi)),
        laser1_lines_per_cm=int(parse_decimal(laser1_lines_per_cm)),
        # Layer 2
        laser2_type=laser2_type if laser2_type else None,
        laser2_power_percent=parse_decimal(laser2_power_percent),
        laser2_speed_mm_s=parse_decimal(laser2_speed_mm_s),
        laser2_passes=int(parse_decimal(laser2_passes)),
        laser2_dpi=int(parse_decimal(laser2_dpi)),
        laser2_lines_per_cm=int(parse_decimal(laser2_lines_per_cm)),
        # Layer 3
        laser3_type=laser3_type if laser3_type else None,
        laser3_power_percent=parse_decimal(laser3_power_percent),
        laser3_speed_mm_s=parse_decimal(laser3_speed_mm_s),
        laser3_passes=int(parse_decimal(laser3_passes)),
        laser3_dpi=int(parse_decimal(laser3_dpi)),
        laser3_lines_per_cm=int(parse_decimal(laser3_lines_per_cm)),
        labor_minutes=parse_decimal(labor_minutes),
        labor_rate_per_hour=parse_decimal(labor_rate_per_hour),
        packaging_cost=parse_decimal(packaging_cost),
        shipping_cost=parse_decimal(shipping_cost),
        notes=notes
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return RedirectResponse(url=f"/products/{product.id}", status_code=303)

# ===== ZUSAMMENBAU (ASSEMBLY) ROUTES =====

@app.get("/products/assembly/new", response_class=HTMLResponse)
async def new_assembly_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neues Zusammenbau-Produkt"""
    # Lade alle Produkte für Verknüpfung
    all_products = db.query(Product).order_by(Product.name).all()
    
    return templates.TemplateResponse("products/form_assembly.html", {
        "request": request,
        "product": None,
        "categories": CATEGORIES,
        "all_products": all_products,
        "title": "Neues Zusammenbau-Produkt"
    })

@app.post("/products/assembly")
async def create_assembly(
    request: Request,
    name: str = Form(...),
    category: str = Form("Sonstiges"),
    labor_minutes: str = Form("0"),
    labor_rate_per_hour: str = Form("20.00"),
    packaging_cost: str = Form("0"),
    shipping_cost: str = Form("0"),
    notes: str = Form(""),
    # Komponenten (dynamische Felder)
    component_name: list[str] = Form([]),
    component_quantity: list[str] = Form([]),
    component_unit_cost: list[str] = Form([]),
    component_notes: list[str] = Form([]),
    component_linked_product_id: list[str] = Form([]),
    db: Session = Depends(get_db)
):
    """Neues Zusammenbau-Produkt erstellen"""
    product = Product(
        name=name,
        product_type="assembly",
        category=category,
        labor_minutes=parse_decimal(labor_minutes),
        labor_rate_per_hour=parse_decimal(labor_rate_per_hour),
        packaging_cost=parse_decimal(packaging_cost),
        shipping_cost=parse_decimal(shipping_cost),
        notes=notes
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Komponenten erstellen
    for i in range(len(component_name)):
        if i < len(component_name) and component_name[i].strip():
            # Wenn ein verknüpftes Produkt ausgewählt wurde, hole dessen Kosten
            linked_id = None
            unit_cost = parse_decimal(component_unit_cost[i]) if i < len(component_unit_cost) else 0
            
            if i < len(component_linked_product_id) and component_linked_product_id[i]:
                try:
                    linked_id = int(component_linked_product_id[i])
                    linked_product = db.query(Product).filter(Product.id == linked_id).first()
                    if linked_product:
                        # Berechne Kosten des verknüpften Produkts
                        linked_calc = linked_product.calculate_costs()
                        unit_cost = linked_calc['total_cost']
                except (ValueError, TypeError):
                    linked_id = None
            
            comp = ProductComponent(
                product_id=product.id,
                name=component_name[i].strip(),
                quantity=parse_decimal(component_quantity[i]) if i < len(component_quantity) else 1,
                unit_cost=unit_cost,
                notes=component_notes[i] if i < len(component_notes) else None,
                linked_product_id=linked_id,
                sort_order=i
            )
            db.add(comp)
    
    db.commit()
    
    return RedirectResponse(url=f"/products/{product.id}", status_code=303)

# ===== PRODUKT ANZEIGEN/BEARBEITEN =====

@app.get("/products/{product_id}", response_class=HTMLResponse)
async def view_product(
    product_id: int, 
    request: Request, 
    success: str = "",
    error: str = "",
    db: Session = Depends(get_db)
):
    """Produktdetails anzeigen"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    
    calculations = product.calculate_costs()
    
    # Lade Bilder des Produkts
    images = db.query(ProductImage).filter(
        ProductImage.product_id == product_id
    ).order_by(ProductImage.is_primary.desc(), ProductImage.created_at.desc()).all()
    
    # Lade Materialien je nach Typ
    filaments = []
    sticker_sheets = []
    laser_materials = []
    all_products = []
    if product.product_type == "3d_print":
        filaments = db.query(Material).filter(Material.material_type == "filament").order_by(Material.name).all()
    elif product.product_type in ["sticker_sheet", "diecut_sticker", "stationery"]:
        sticker_sheets = db.query(Material).filter(Material.material_type == "sticker_sheet").order_by(Material.name).all()
    elif product.product_type == "laser_engraving":
        laser_materials = db.query(Material).filter(Material.material_type == "laser_material").order_by(Material.name).all()
    elif product.product_type == "assembly":
        # Lade alle Produkte für Verknüpfungs-Anzeige
        all_products = db.query(Product).filter(Product.id != product_id).order_by(Product.name).all()
    
    # Lade Maschinen je nach Typ (nur für 3D-Druck)
    machines = []
    if product.product_type == "3d_print":
        machines = db.query(Machine).filter(Machine.machine_type == "3d_printer").order_by(Machine.name).all()
    
    return templates.TemplateResponse("products/detail.html", {
        "request": request,
        "product": product,
        "calc": calculations,
        "categories": CATEGORIES,
        "filaments": filaments,
        "sticker_sheets": sticker_sheets,
        "laser_materials": laser_materials,
        "machines": machines,
        "images": images,
        "all_products": all_products,
        "success_msg": success,
        "error_msg": error
    })

@app.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def edit_product_form(product_id: int, request: Request, db: Session = Depends(get_db)):
    """Produkt bearbeiten - typ-spezifisches Formular"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    
    # Lade entsprechende Materialien
    filaments = db.query(Material).filter(Material.material_type == "filament").order_by(Material.name).all()
    sticker_sheets = db.query(Material).filter(Material.material_type == "sticker_sheet").order_by(Material.name).all()
    laser_materials = db.query(Material).filter(Material.material_type == "laser_material").order_by(Material.name).all()
    
    # Lade entsprechende Maschinen
    machines = []
    if product.product_type == "3d_print":
        machines = db.query(Machine).filter(Machine.machine_type == "3d_printer").order_by(Machine.name).all()
    elif product.product_type in ["sticker_sheet", "diecut_sticker", "stationery"]:
        # Alle Maschinen laden
        machines = db.query(Machine).order_by(Machine.name).all()
    
    # Wähle das richtige Template je nach Produkttyp
    if product.product_type == "3d_print":
        template = "products/form_3d_print.html"
    elif product.product_type == "sticker_sheet":
        template = "products/form_sticker_sheet.html"
    elif product.product_type == "diecut_sticker":
        template = "products/form_diecut_sticker.html"
    elif product.product_type == "stationery":
        template = "products/form_stationery.html"
    elif product.product_type == "laser_engraving":
        template = "products/form_laser_engraving.html"
    elif product.product_type == "assembly":
        template = "products/form_assembly.html"
        # Lade alle Produkte für Verknüpfung
        all_products = db.query(Product).order_by(Product.name).all()
        return templates.TemplateResponse(template, {
            "request": request,
            "product": product,
            "categories": CATEGORIES,
            "all_products": all_products,
            "title": f"Produkt bearbeiten"
        })
    else:
        template = "products/form_generic.html"
    
    return templates.TemplateResponse(template, {
        "request": request,
        "product": product,
        "categories": CATEGORIES,
        "filaments": filaments,
        "sticker_sheets": sticker_sheets,
        "laser_materials": laser_materials,
        "machines": machines,
        "title": f"Produkt bearbeiten"
    })

@app.post("/products/{product_id}/update")
async def update_product(
    product_id: int,
    request: Request,
    name: str = Form(...),
    category: str = Form("Sonstiges"),
    # 3D-Druck Felder
    filament_material_id: int = Form(None),
    filament_weight_g: str = Form(None),
    print_time_hours: str = Form("0"),
    # Sticker Felder
    sheet_material_id: int = Form(None),
    sheet_count: str = Form(None),
    units_per_sheet: str = Form("1"),
    units_per_batch: str = Form("1"),
    calculation_mode: str = Form("per_unit"),
    cut_time_hours: str = Form("0"),
    # Laser-Gravur Felder - Layer 1
    laser_material_id: int = Form(None),
    laser_design_name: str = Form(None),
    laser1_type: str = Form(None),
    laser1_power_percent: str = Form("80.0"),
    laser1_speed_mm_s: str = Form("200"),
    laser1_passes: str = Form("1"),
    laser1_dpi: str = Form("300"),
    laser1_lines_per_cm: str = Form("60"),
    # Laser-Gravur Felder - Layer 2
    laser2_type: str = Form(None),
    laser2_power_percent: str = Form("100.0"),
    laser2_speed_mm_s: str = Form("100"),
    laser2_passes: str = Form("1"),
    laser2_dpi: str = Form("300"),
    laser2_lines_per_cm: str = Form("60"),
    # Laser-Gravur Felder - Layer 3
    laser3_type: str = Form(None),
    laser3_power_percent: str = Form("50.0"),
    laser3_speed_mm_s: str = Form("300"),
    laser3_passes: str = Form("1"),
    laser3_dpi: str = Form("600"),
    laser3_lines_per_cm: str = Form("120"),
    # Gemeinsame Felder
    machine_id: int = Form(None),
    labor_minutes: str = Form("0"),
    labor_rate_per_hour: str = Form("20.00"),
    packaging_cost: str = Form("0"),
    shipping_cost: str = Form("0"),
    notes: str = Form(""),
    # Mehrere Maschinen (für Sticker, Schreibwaren, DieCut)
    machine_ids: list[int] = Form([]),
    # Assembly Komponenten (dynamische Felder)
    component_id: list[str] = Form([]),
    component_name: list[str] = Form([]),
    component_quantity: list[str] = Form([]),
    component_unit_cost: list[str] = Form([]),
    component_notes: list[str] = Form([]),
    component_linked_product_id: list[str] = Form([]),
    db: Session = Depends(get_db)
):
    """Produkt aktualisieren"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    
    product.name = name
    product.category = category
    
    # Typ-spezifische Felder
    if product.product_type == "3d_print":
        product.filament_material_id = filament_material_id
        product.filament_weight_g = parse_decimal(filament_weight_g) if filament_weight_g else None
        product.print_time_hours = parse_decimal(print_time_hours)
    elif product.product_type in ["sticker_sheet", "diecut_sticker", "stationery"]:
        product.sheet_material_id = sheet_material_id
        product.sheet_count = 1  # Immer 1
        product.calculation_mode = calculation_mode
        if calculation_mode == "per_unit":
            product.units_per_sheet = parse_decimal(units_per_sheet)
            product.units_per_batch = 1
        else:
            product.units_per_batch = int(units_per_batch)
            product.units_per_sheet = 1
        # Mehrere Maschinen speichern
        product.machine_id = machine_ids[0] if machine_ids else None
        product.additional_machine_ids = ",".join(str(mid) for mid in machine_ids[1:]) if len(machine_ids) > 1 else None
    elif product.product_type == "laser_engraving":
        product.laser_material_id = laser_material_id
        product.laser_design_name = laser_design_name
        # Layer 1
        product.laser1_type = laser1_type
        product.laser1_power_percent = parse_decimal(laser1_power_percent)
        product.laser1_speed_mm_s = parse_decimal(laser1_speed_mm_s)
        product.laser1_passes = int(parse_decimal(laser1_passes))
        product.laser1_dpi = int(parse_decimal(laser1_dpi))
        product.laser1_lines_per_cm = int(parse_decimal(laser1_lines_per_cm))
        # Layer 2
        product.laser2_type = laser2_type if laser2_type else None
        product.laser2_power_percent = parse_decimal(laser2_power_percent)
        product.laser2_speed_mm_s = parse_decimal(laser2_speed_mm_s)
        product.laser2_passes = int(parse_decimal(laser2_passes))
        product.laser2_dpi = int(parse_decimal(laser2_dpi))
        product.laser2_lines_per_cm = int(parse_decimal(laser2_lines_per_cm))
        # Layer 3
        product.laser3_type = laser3_type if laser3_type else None
        product.laser3_power_percent = parse_decimal(laser3_power_percent)
        product.laser3_speed_mm_s = parse_decimal(laser3_speed_mm_s)
        product.laser3_passes = int(parse_decimal(laser3_passes))
        product.laser3_dpi = int(parse_decimal(laser3_dpi))
        product.laser3_lines_per_cm = int(parse_decimal(laser3_lines_per_cm))
    elif product.product_type == "assembly":
        # Lösche bestehende Komponenten und erstelle neue
        db.query(ProductComponent).filter(ProductComponent.product_id == product_id).delete()
        
        # Komponenten erstellen
        for i in range(len(component_name)):
            if i < len(component_name) and component_name[i].strip():
                # Wenn ein verknüpftes Produkt ausgewählt wurde, hole dessen Kosten
                linked_id = None
                unit_cost = parse_decimal(component_unit_cost[i]) if i < len(component_unit_cost) else 0
                
                if i < len(component_linked_product_id) and component_linked_product_id[i]:
                    try:
                        linked_id = int(component_linked_product_id[i])
                        linked_product = db.query(Product).filter(Product.id == linked_id).first()
                        if linked_product:
                            # Berechne Kosten des verknüpften Produkts
                            linked_calc = linked_product.calculate_costs()
                            unit_cost = linked_calc['total_cost']
                    except (ValueError, TypeError):
                        linked_id = None
                
                comp = ProductComponent(
                    product_id=product.id,
                    name=component_name[i].strip(),
                    quantity=parse_decimal(component_quantity[i]) if i < len(component_quantity) else 1,
                    unit_cost=unit_cost,
                    notes=component_notes[i] if i < len(component_notes) else None,
                    linked_product_id=linked_id,
                    sort_order=i
                )
                db.add(comp)
    
    # Gemeinsame Felder
    if product.product_type == "3d_print":
        product.machine_id = machine_id
    product.labor_minutes = parse_decimal(labor_minutes)
    product.labor_rate_per_hour = parse_decimal(labor_rate_per_hour)
    
    # Verpackung/Versand nur für 3D-Druck und Laser (bei Sticker/Schreibwaren wird es beim Verkauf erfasst)
    if product.product_type in ["3d_print", "laser_engraving"]:
        product.packaging_cost = parse_decimal(packaging_cost)
        product.shipping_cost = parse_decimal(shipping_cost)
    else:
        product.packaging_cost = 0
        product.shipping_cost = 0
    
    product.notes = notes
    product.updated_at = datetime.utcnow()
    
    db.commit()
    
    return RedirectResponse(url=f"/products/{product_id}", status_code=303)

@app.post("/products/{product_id}/delete")
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Produkt löschen"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    
    # Lösche zuerst alle Komponenten (falls Assembly-Produkt)
    db.query(ProductComponent).filter(ProductComponent.product_id == product_id).delete()
    
    db.delete(product)
    db.commit()
    
    return RedirectResponse(url="/products", status_code=303)

# ===== FEEDBACK ROUTES =====

@app.get("/feedback", response_class=HTMLResponse)
async def feedback_form(request: Request, page: str = "/", title: str = ""):
    """Feedback-Formular anzeigen"""
    return templates.TemplateResponse("feedback/form.html", {
        "request": request,
        "page_url": page,
        "page_title": title,
        "title": "Feedback senden"
    })

@app.post("/feedback")
async def submit_feedback(
    request: Request,
    page_url: str = Form(...),
    page_title: str = Form(""),
    category: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db)
):
    """Feedback speichern"""
    feedback = Feedback(
        page_url=page_url,
        page_title=page_title,
        category=category,
        message=message,
        status="new"
    )
    
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    
    # Zurück zur vorherigen Seite mit Erfolgsmeldung
    response = RedirectResponse(url=page_url, status_code=303)
    return response

@app.get("/feedback/list", response_class=HTMLResponse)
async def list_feedback(request: Request, db: Session = Depends(get_db)):
    """Alle Feedback-Einträge anzeigen (Admin-Ansicht)"""
    feedbacks = db.query(Feedback).order_by(Feedback.created_at.desc()).all()
    
    return templates.TemplateResponse("feedback/list.html", {
        "request": request,
        "feedbacks": feedbacks,
        "title": "Feedback Übersicht"
    })

@app.post("/feedback/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    """Status eines Feedback-Eintrags aktualisieren"""
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback nicht gefunden")
    
    feedback.status = status
    feedback.updated_at = datetime.utcnow()
    db.commit()
    
    return RedirectResponse(url="/feedback/list", status_code=303)

@app.post("/feedback/{feedback_id}/delete")
async def delete_feedback(feedback_id: int, db: Session = Depends(get_db)):
    """Feedback-Eintrag löschen"""
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback nicht gefunden")
    
    db.delete(feedback)
    db.commit()
    
    return RedirectResponse(url="/feedback/list", status_code=303)

# ===== IDEEN-BOARD ROUTES =====

@app.get("/ideas", response_class=HTMLResponse)
async def ideas_board(request: Request, db: Session = Depends(get_db)):
    """Kanban-Style Ideen-Board anzeigen"""
    ideas_todo = db.query(Idea).filter(Idea.status == "todo").order_by(Idea.created_at.desc()).all()
    ideas_in_progress = db.query(Idea).filter(Idea.status == "in_progress").order_by(Idea.created_at.desc()).all()
    ideas_done = db.query(Idea).filter(Idea.status == "done").order_by(Idea.created_at.desc()).all()
    
    return templates.TemplateResponse("ideas/board.html", {
        "request": request,
        "ideas_todo": ideas_todo,
        "ideas_in_progress": ideas_in_progress,
        "ideas_done": ideas_done,
        "title": "Ideen-Board"
    })

@app.post("/ideas")
async def create_idea(
    request: Request,
    subject: str = Form(...),
    content: str = Form(""),
    status: str = Form("todo"),
    db: Session = Depends(get_db)
):
    """Neue Idee erstellen"""
    idea = Idea(
        subject=subject,
        content=content,
        status=status
    )
    
    db.add(idea)
    db.commit()
    db.refresh(idea)
    
    return RedirectResponse(url="/ideas", status_code=303)

@app.post("/ideas/{idea_id}/update")
async def update_idea(
    idea_id: int,
    request: Request,
    subject: str = Form(...),
    content: str = Form(""),
    status: str = Form("todo"),
    db: Session = Depends(get_db)
):
    """Idee aktualisieren"""
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idee nicht gefunden")
    
    idea.subject = subject
    idea.content = content
    idea.status = status
    idea.updated_at = datetime.utcnow()
    
    db.commit()
    
    return RedirectResponse(url="/ideas", status_code=303)

@app.post("/ideas/{idea_id}/delete")
async def delete_idea(idea_id: int, db: Session = Depends(get_db)):
    """Idee löschen"""
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idee nicht gefunden")
    
    db.delete(idea)
    db.commit()
    
    return RedirectResponse(url="/ideas", status_code=303)


@app.post("/ideas/{idea_id}/status")
async def update_idea_status(
    idea_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    """Nur Status einer Idee aktualisieren (für Drag & Drop)"""
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idee nicht gefunden")
    
    idea.status = status
    idea.updated_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "id": idea_id, "status": status}


# ========================================
# SALES ORDERS - VERKAUFSAUFTRÄGE
# ========================================

@app.get("/sales-orders", response_class=HTMLResponse)
async def list_sales_orders(request: Request, db: Session = Depends(get_db)):
    """Liste aller Verkaufsaufträge"""
    orders = db.query(SalesOrder).order_by(SalesOrder.created_at.desc()).all()
    return templates.TemplateResponse("sales_orders/list.html", {
        "request": request,
        "orders": orders
    })

@app.get("/sales-orders/new", response_class=HTMLResponse)
async def new_sales_order_form(request: Request, product_id: int = None, db: Session = Depends(get_db)):
    """Formular für neuen Verkaufsauftrag"""
    products = db.query(Product).order_by(Product.name).all()
    product = None
    if product_id:
        product = db.query(Product).filter(Product.id == product_id).first()
    return templates.TemplateResponse("sales_orders/form.html", {
        "request": request,
        "order": None,
        "products": products,
        "product": product,
        "title": "Neuer Verkaufsauftrag"
    })

@app.post("/sales-orders")
async def create_sales_order(
    request: Request,
    order_number: str = Form(""),
    customer_name: str = Form(""),
    packaging_cost: str = Form("0"),
    shipping_cost: str = Form("0"),
    labor_minutes_packaging: str = Form("0"),
    labor_rate_packaging: str = Form("20.00"),
    notes: str = Form(""),
    # Dynamische Felder für Produkte (Arrays)
    product_id: list[int] = Form([]),
    quantity: list[str] = Form([]),
    unit_price: list[str] = Form([]),
    production_cost_per_unit: list[str] = Form([]),
    db: Session = Depends(get_db)
):
    """Neuen Verkaufsauftrag mit mehreren Produkten erstellen"""
    
    # Auftrag (Header) erstellen
    order = SalesOrder(
        order_number=order_number if order_number else None,
        customer_name=customer_name if customer_name else None,
        packaging_cost=parse_decimal(packaging_cost),
        shipping_cost=parse_decimal(shipping_cost),
        labor_minutes_packaging=parse_decimal(labor_minutes_packaging),
        labor_rate_packaging=parse_decimal(labor_rate_packaging),
        notes=notes if notes else None,
        status="pending"
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
    # Auftragspositionen erstellen
    for i in range(len(product_id)):
        if i < len(quantity) and i < len(unit_price):
            item = SalesOrderItem(
                sales_order_id=order.id,
                product_id=product_id[i],
                quantity=int(quantity[i]),
                unit_price=parse_decimal(unit_price[i]),
                production_cost_per_unit=parse_decimal(production_cost_per_unit[i]) if i < len(production_cost_per_unit) else 0
            )
            db.add(item)
    
    db.commit()
    return RedirectResponse(url=f"/sales-orders/{order.id}", status_code=303)

@app.get("/sales-orders/{order_id}", response_class=HTMLResponse)
async def view_sales_order(order_id: int, request: Request, db: Session = Depends(get_db)):
    """Verkaufsauftrag anzeigen"""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
    
    return templates.TemplateResponse("sales_orders/detail.html", {
        "request": request,
        "order": order
    })

@app.post("/sales-orders/{order_id}/status")
async def update_sales_order_status(
    order_id: int,
    request: Request,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    """Status des Verkaufsauftrags aktualisieren"""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
    
    order.status = status
    if status == "produced":
        order.produced_at = datetime.utcnow()
    elif status == "shipped":
        order.shipped_at = datetime.utcnow()
    
    db.commit()
    return RedirectResponse(url=f"/sales-orders/{order.id}", status_code=303)

# ========================================
# TOOLS - PNG TO SVG CONVERTER
# ========================================

# Verzeichnis für temporäre Uploads
UPLOAD_DIR = Path("/tmp/picocalc_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Permanentes Speicherverzeichnis (Docker Volume)
FILE_STORAGE_PATH = Path(os.environ.get("FILE_STORAGE_PATH", "/app/storage"))
FILE_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

@app.get("/tools/png-to-svg", response_class=HTMLResponse)
async def png_to_svg_form(request: Request, error: str = "", success: str = ""):
    """PNG zu SVG Converter - Upload Formular"""
    return templates.TemplateResponse("tools/png_to_svg.html", {
        "request": request,
        "title": "PNG zu SVG Converter",
        "error": error,
        "success": success,
        "svg_content": None,
        "original_filename": None
    })

@app.post("/tools/png-to-svg")
async def png_to_svg_convert(
    request: Request,
    image: UploadFile = File(...),
    mode: str = Form("spline"),
    color_mode: str = Form("color"),
    filter_speckle: int = Form(4),
    color_precision: int = Form(6),
    layer_difference: int = Form(16),
    corner_threshold: int = Form(60),
    save_file: str = Form("true"),  # 'true' oder 'false'
    description: str = Form(""),
    tags: str = Form(""),
    db: Session = Depends(get_db)
):
    """PNG/JPG zu SVG konvertieren und optional speichern"""
    
    # Prüfe Dateityp
    allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/bmp']
    if image.content_type not in allowed_types:
        return templates.TemplateResponse("tools/png_to_svg.html", {
            "request": request,
            "title": "PNG zu SVG Converter",
            "error": "Nur PNG, JPG, WEBP oder BMP Dateien erlaubt.",
            "success": "",
            "svg_content": None,
            "original_filename": None
        })
    
    try:
        # Generiere eindeutige Dateinamen
        file_id = str(uuid.uuid4())
        input_path = UPLOAD_DIR / f"{file_id}_input.png"
        output_path = UPLOAD_DIR / f"{file_id}_output.svg"
        
        # Speichere hochgeladene Datei
        content = await image.read()
        with open(input_path, "wb") as f:
            f.write(content)
        
        # Konvertiere zu SVG mit vtracer
        vtracer.convert_image_to_svg_py(
            str(input_path),
            str(output_path),
            colormode=color_mode,           # 'color' oder 'binary'
            mode=mode,                      # 'spline', 'polygon', oder 'none'
            filter_speckle=filter_speckle,  # Default: 4
            color_precision=color_precision,# Default: 6
            layer_difference=layer_difference,  # Default: 16
            corner_threshold=corner_threshold,  # Default: 60
        )
        
        # Lese generierte SVG
        with open(output_path, "r", encoding="utf-8") as f:
            svg_content = f.read()
        
        # Berechne Dateigrößen
        original_size = len(content)
        svg_size = len(svg_content.encode('utf-8'))
        
        # Wenn speichern aktiviert, in permanenten Speicher verschieben
        db_entry = None
        if save_file == "true":
            # Erstelle Unterordner basierend auf Datum für bessere Organisation
            from datetime import datetime
            date_folder = datetime.now().strftime("%Y/%m")
            storage_subdir = FILE_STORAGE_PATH / date_folder
            storage_subdir.mkdir(parents=True, exist_ok=True)
            
            # Permanente Pfade
            png_filename = f"{file_id}.png"
            svg_filename = f"{file_id}.svg"
            png_path = storage_subdir / png_filename
            svg_path = storage_subdir / svg_filename
            
            # Kopiere Dateien in permanenten Speicher
            import shutil
            shutil.copy(input_path, png_path)
            shutil.copy(output_path, svg_path)
            
            # Datenbank-Eintrag erstellen
            db_entry = ConvertedFile(
                original_filename=image.filename,
                stored_filename=file_id,
                file_path_png=str(Path(date_folder) / png_filename),
                file_path_svg=str(Path(date_folder) / svg_filename),
                original_size_bytes=original_size,
                svg_size_bytes=svg_size,
                conversion_mode=mode,
                color_mode=color_mode,
                description=description if description else None,
                tags=tags if tags else None
            )
            db.add(db_entry)
            db.commit()
            db.refresh(db_entry)
        
        # Lösche temporäre Dateien
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        
        return templates.TemplateResponse("tools/png_to_svg.html", {
            "request": request,
            "title": "PNG zu SVG Converter - Ergebnis",
            "error": "",
            "success": f"Konvertierung erfolgreich! Original: {original_size/1024:.1f} KB, SVG: {svg_size/1024:.1f} KB" + (" (Gespeichert)" if db_entry else " (Nicht gespeichert)"),
            "svg_content": svg_content,
            "original_filename": image.filename,
            "original_size": original_size,
            "svg_size": svg_size,
            "saved_file_id": db_entry.id if db_entry else None
        })
        
    except Exception as e:
        # Cleanup bei Fehler
        if 'input_path' in locals():
            input_path.unlink(missing_ok=True)
        if 'output_path' in locals():
            output_path.unlink(missing_ok=True)
        
        return templates.TemplateResponse("tools/png_to_svg.html", {
            "request": request,
            "title": "PNG zu SVG Converter",
            "error": f"Fehler bei der Konvertierung: {str(e)}",
            "success": "",
            "svg_content": None,
            "original_filename": None
        })

@app.get("/tools/converted-files", response_class=HTMLResponse)
async def list_converted_files(
    request: Request,
    search: str = "",
    db: Session = Depends(get_db)
):
    """Liste aller gespeicherten Konvertierungen"""
    query = db.query(ConvertedFile)
    
    if search:
        query = query.filter(
            (ConvertedFile.original_filename.ilike(f"%{search}%")) |
            (ConvertedFile.description.ilike(f"%{search}%")) |
            (ConvertedFile.tags.ilike(f"%{search}%"))
        )
    
    files = query.order_by(ConvertedFile.created_at.desc()).all()
    
    return templates.TemplateResponse("tools/converted_files_list.html", {
        "request": request,
        "title": "Gespeicherte Konvertierungen",
        "files": files,
        "search": search
    })

@app.get("/tools/converted-files/{file_id}/preview", response_class=HTMLResponse)
async def preview_converted_file(
    file_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Vorschau einer gespeicherten Konvertierung"""
    file_entry = db.query(ConvertedFile).filter(ConvertedFile.id == file_id).first()
    if not file_entry:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    # Lese SVG-Inhalt
    svg_path = FILE_STORAGE_PATH / file_entry.file_path_svg
    if not svg_path.exists():
        raise HTTPException(status_code=404, detail="SVG-Datei nicht gefunden")
    
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read()
    
    return templates.TemplateResponse("tools/converted_file_preview.html", {
        "request": request,
        "title": f"Vorschau: {file_entry.original_filename}",
        "file": file_entry,
        "svg_content": svg_content
    })

@app.get("/tools/converted-files/{file_id}/download/svg")
async def download_svg(file_id: int, db: Session = Depends(get_db)):
    """Download der SVG-Datei"""
    file_entry = db.query(ConvertedFile).filter(ConvertedFile.id == file_id).first()
    if not file_entry:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    svg_path = FILE_STORAGE_PATH / file_entry.file_path_svg
    if not svg_path.exists():
        raise HTTPException(status_code=404, detail="SVG-Datei nicht gefunden")
    
    return FileResponse(
        path=svg_path,
        filename=file_entry.original_filename.replace('.png', '.svg').replace('.jpg', '.svg'),
        media_type="image/svg+xml"
    )

@app.get("/tools/converted-files/{file_id}/download/png")
async def download_png(file_id: int, db: Session = Depends(get_db)):
    """Download der originalen PNG-Datei"""
    file_entry = db.query(ConvertedFile).filter(ConvertedFile.id == file_id).first()
    if not file_entry:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    png_path = FILE_STORAGE_PATH / file_entry.file_path_png
    if not png_path.exists():
        raise HTTPException(status_code=404, detail="PNG-Datei nicht gefunden")
    
    return FileResponse(
        path=png_path,
        filename=file_entry.original_filename,
        media_type="image/png"
    )

@app.post("/tools/converted-files/{file_id}/delete")
async def delete_converted_file(file_id: int, db: Session = Depends(get_db)):
    """Lösche eine gespeicherte Konvertierung"""
    file_entry = db.query(ConvertedFile).filter(ConvertedFile.id == file_id).first()
    if not file_entry:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    # Lösche physische Dateien
    png_path = FILE_STORAGE_PATH / file_entry.file_path_png
    svg_path = FILE_STORAGE_PATH / file_entry.file_path_svg
    
    png_path.unlink(missing_ok=True)
    svg_path.unlink(missing_ok=True)
    
    # Lösche DB-Eintrag
    db.delete(file_entry)
    db.commit()
    
    return RedirectResponse(url="/tools/converted-files", status_code=303)


# ========================================
# PRODUKT BILDER - UPLOAD UND VERWALTUNG
# ========================================

@app.post("/products/{product_id}/images/upload")
async def upload_product_image(
    product_id: int,
    request: Request,
    image: UploadFile = File(...),
    description: str = Form(""),
    is_primary: int = Form(0),
    db: Session = Depends(get_db)
):
    """Lade ein Produktbild hoch (PNG, JPG - ohne SVG-Konvertierung)"""
    
    # Prüfe ob Produkt existiert
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    
    # Prüfe Dateityp
    allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp']
    if image.content_type not in allowed_types:
        return RedirectResponse(
            url=f"/products/{product_id}?error=Nur PNG, JPG oder WEBP erlaubt", 
            status_code=303
        )
    
    try:
        # Generiere eindeutigen Dateinamen
        file_id = str(uuid.uuid4())
        date_folder = datetime.now().strftime("%Y/%m")
        storage_subdir = FILE_STORAGE_PATH / "products" / date_folder
        storage_subdir.mkdir(parents=True, exist_ok=True)
        
        # Dateiendung bestimmen
        ext = image.filename.split('.')[-1].lower()
        if ext not in ['png', 'jpg', 'jpeg', 'webp']:
            ext = 'png'
        
        filename = f"{file_id}.{ext}"
        file_path = storage_subdir / filename
        
        # Speichere Datei
        content = await image.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Falls is_primary gesetzt, setze alle anderen Bilder auf nicht-primary
        if is_primary:
            db.query(ProductImage).filter(
                ProductImage.product_id == product_id
            ).update({"is_primary": 0})
        
        # Datenbank-Eintrag erstellen
        product_image = ProductImage(
            product_id=product_id,
            original_filename=image.filename,
            stored_filename=file_id,
            file_path=str(Path("products") / date_folder / filename),
            file_size_bytes=len(content),
            mime_type=image.content_type,
            description=description if description else None,
            is_primary=is_primary
        )
        db.add(product_image)
        db.commit()
        
        return RedirectResponse(
            url=f"/products/{product_id}?success=Bild erfolgreich hochgeladen", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/products/{product_id}?error=Fehler beim Upload: {str(e)}", 
            status_code=303
        )


@app.get("/product-images/{image_id}")
async def get_product_image(image_id: int, db: Session = Depends(get_db)):
    """Zeige ein Produktbild an"""
    image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    
    file_path = FILE_STORAGE_PATH / image.file_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    return FileResponse(
        path=file_path,
        media_type=image.mime_type or "image/png"
    )


@app.post("/product-images/{image_id}/delete")
async def delete_product_image(image_id: int, db: Session = Depends(get_db)):
    """Lösche ein Produktbild"""
    image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    
    product_id = image.product_id
    
    # Lösche physische Datei
    file_path = FILE_STORAGE_PATH / image.file_path
    file_path.unlink(missing_ok=True)
    
    # Lösche DB-Eintrag
    db.delete(image)
    db.commit()
    
    return RedirectResponse(url=f"/products/{product_id}", status_code=303)


@app.post("/product-images/{image_id}/set-primary")
async def set_primary_image(image_id: int, db: Session = Depends(get_db)):
    """Setze ein Bild als Hauptbild"""
    image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    
    # Setze alle Bilder des Produkts auf nicht-primary
    db.query(ProductImage).filter(
        ProductImage.product_id == image.product_id
    ).update({"is_primary": 0})
    
    # Setze dieses Bild als primary
    image.is_primary = 1
    db.commit()
    
    return RedirectResponse(url=f"/products/{image.product_id}", status_code=303)


@app.post("/products/{product_id}/images/link-svg")
async def link_svg_to_product(
    product_id: int,
    converted_file_id: int = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Verknüpfe ein SVG aus der Bibliothek mit einem Produkt"""
    
    # Prüfe ob Produkt und SVG existieren
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    
    converted_file = db.query(ConvertedFile).filter(ConvertedFile.id == converted_file_id).first()
    if not converted_file:
        raise HTTPException(status_code=404, detail="SVG nicht gefunden")
    
    # Erstelle Verknüpfung
    product_image = ProductImage(
        product_id=product_id,
        original_filename=converted_file.original_filename,
        stored_filename=converted_file.stored_filename,
        file_path=converted_file.file_path_png,  # Wir zeigen die PNG-Vorschau an
        file_size_bytes=converted_file.original_size_bytes,
        mime_type="image/png",
        description=description if description else converted_file.description,
        converted_file_id=converted_file_id
    )
    db.add(product_image)
    db.commit()
    
    return RedirectResponse(
        url=f"/products/{product_id}?success=SVG erfolgreich verknüpft", 
        status_code=303
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
