from fastapi import FastAPI, Request, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from database import engine, get_db, SessionLocal
from models import (
    Base, Product, Material, MaterialType, Machine, ProductComponent,
    FeedbackIdea, ConvertedFile, MarketEvent, EventItem, EventTodo, STROM_PREIS_KWH
)
from datetime import datetime
from pathlib import Path
import time
import uuid
import os
import shutil
import vtracer


def parse_decimal(value: str) -> float:
    """Konvertiert einen String mit Komma oder Punkt als Dezimaltrenner zu float"""
    if value is None or str(value).strip() == '':
        return 0.0
    return float(str(value).replace(',', '.'))


def seed_material_types(db: Session):
    """Initialisiert Standard-Materialtypen falls noch keine existieren"""
    existing = db.query(MaterialType).first()
    if existing:
        return
    
    default_types = [
        ("filament", "3D-Filament (€/kg)", "Filament für 3D-Drucker", 1),
        ("sticker_sheet", "Sticker-Sheet (€/Bogen)", "Bögen für Sticker", 2),
        ("diecut_sticker", "DieCut-Sticker Material", "Material für einzelne Sticker", 3),
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

# Static Files
app.mount("/static", StaticFiles(directory="assets"), name="static")

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
    ("sticker", "Sticker"),
]

# Sticker-Kategorien (für Sticker-Produkttyp)
STICKER_CATEGORIES = [
    ("StickerSheet", "Sticker-Sheet (ganzer Bogen)"),
    ("DieCut", "DieCut-Sticker (einzeln geschnitten)"),
]


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard mit Übersicht"""
    products = db.query(Product).order_by(Product.updated_at.desc()).limit(5).all()
    total_products = db.query(Product).count()
    total_materials = db.query(Material).count()
    total_machines = db.query(Machine).count()
    
    # Anstehende Events für das Dashboard
    upcoming_events = db.query(MarketEvent).filter(
        MarketEvent.status.in_(["planning", "in_production", "ready"])
    ).order_by(MarketEvent.event_date.asc().nullslast(), MarketEvent.created_at.desc()).limit(3).all()
    
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
        "upcoming_events": upcoming_events
    })


# =============================================================================
# MATERIAL ROUTES
# =============================================================================

@app.get("/materials", response_class=HTMLResponse)
async def list_materials(
    request: Request,
    material_type: str = "",
    search: str = "",
    sort_by: str = "name",
    sort_order: str = "asc",
    db: Session = Depends(get_db)
):
    """Liste aller Materialien"""
    query = db.query(Material)
    if material_type:
        query = query.filter(Material.material_type == material_type)
    if search:
        query = query.filter(
            (Material.name.ilike(f"%{search}%")) |
            (Material.brand.ilike(f"%{search}%")) |
            (Material.color.ilike(f"%{search}%"))
        )
    
    sort_col = Material.name
    if sort_by == "type":
        sort_col = Material.material_type
    elif sort_by == "price":
        sort_col = Material.price_per_unit
    
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())
    
    materials = query.all()
    material_types = get_material_types(db)
    
    return templates.TemplateResponse("materials/list.html", {
        "request": request,
        "materials": materials,
        "material_type": material_type,
        "material_types": material_types,
        "search": search,
        "sort_by": sort_by,
        "sort_order": sort_order
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
    """Material bearbeiten"""
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


# =============================================================================
# MATERIAL TYPEN ROUTES
# =============================================================================

@app.get("/material-types", response_class=HTMLResponse)
async def list_material_types(
    request: Request,
    search: str = "",
    sort_by: str = "name",
    sort_order: str = "asc",
    db: Session = Depends(get_db)
):
    """Liste aller Materialtypen"""
    query = db.query(MaterialType)
    
    if search:
        query = query.filter(
            (MaterialType.name.ilike(f"%{search}%")) |
            (MaterialType.key.ilike(f"%{search}%"))
        )
    
    sort_col = MaterialType.name
    if sort_by == "sort_order":
        sort_col = MaterialType.sort_order
    elif sort_by == "key":
        sort_col = MaterialType.key
    
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())
    
    material_types = query.all()
    return templates.TemplateResponse("materials/type_list.html", {
        "request": request,
        "material_types": material_types,
        "search": search,
        "sort_by": sort_by,
        "sort_order": sort_order
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
    material_type = MaterialType(
        key=key,
        name=name,
        description=description,
        sort_order=sort_order
    )
    db.add(material_type)
    db.commit()
    db.refresh(material_type)
    return RedirectResponse(url="/material-types", status_code=303)


@app.get("/material-types/{type_id}/edit", response_class=HTMLResponse)
async def edit_material_type_form(type_id: int, request: Request, db: Session = Depends(get_db)):
    """Materialtyp bearbeiten"""
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
    """Materialtyp löschen"""
    material_type = db.query(MaterialType).filter(MaterialType.id == type_id).first()
    if not material_type:
        raise HTTPException(status_code=404, detail="Materialtyp nicht gefunden")
    
    # Prüfe ob Materialien diesen Typ verwenden
    usage_count = db.query(Material).filter(Material.material_type == material_type.key).count()
    if usage_count > 0:
        # Soft-delete: auf inaktiv setzen
        material_type.is_active = 0
        db.commit()
    else:
        db.delete(material_type)
        db.commit()
    
    return RedirectResponse(url="/material-types", status_code=303)


# =============================================================================
# MASCHINEN ROUTES
# =============================================================================

@app.get("/machines", response_class=HTMLResponse)
async def list_machines(
    request: Request,
    search: str = "",
    sort_by: str = "name",
    sort_order: str = "asc",
    db: Session = Depends(get_db)
):
    """Liste aller Maschinen"""
    query = db.query(Machine)
    
    if search:
        query = query.filter(
            (Machine.name.ilike(f"%{search}%")) |
            (Machine.description.ilike(f"%{search}%"))
        )
    
    sort_col = Machine.name
    if sort_by == "type":
        sort_col = Machine.machine_type
    elif sort_by == "depreciation":
        sort_col = Machine.depreciation_euro
    
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())
    
    machines = query.all()
    return templates.TemplateResponse("machines/list.html", {
        "request": request,
        "machines": machines,
        "search": search,
        "sort_by": sort_by,
        "sort_order": sort_order
    })


@app.get("/machines/new", response_class=HTMLResponse)
async def new_machine_form(request: Request):
    """Formular für neue Maschine"""
    return templates.TemplateResponse("machines/form.html", {
        "request": request,
        "machine": None,
        "title": "Neue Maschine"
    })


@app.post("/machines")
async def create_machine(
    request: Request,
    name: str = Form(...),
    machine_type: str = Form(...),
    description: str = Form(""),
    depreciation_euro: str = Form("0"),
    lifespan_hours: str = Form("1"),
    power_kw: str = Form("0"),
    lifespan_pages: str = Form(""),
    depreciation_per_page: str = Form(""),
    cost_per_sheet: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neue Maschine erstellen"""
    machine = Machine(
        name=name,
        machine_type=machine_type,
        description=description,
        depreciation_euro=parse_decimal(depreciation_euro),
        lifespan_hours=parse_decimal(lifespan_hours) or 1,
        power_kw=parse_decimal(power_kw),
        lifespan_pages=parse_decimal(lifespan_pages) if lifespan_pages else None,
        depreciation_per_page=parse_decimal(depreciation_per_page) if depreciation_per_page else None,
        cost_per_sheet=parse_decimal(cost_per_sheet) if cost_per_sheet else None
    )
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return RedirectResponse(url="/machines", status_code=303)


@app.get("/machines/{machine_id}/edit", response_class=HTMLResponse)
async def edit_machine_form(machine_id: int, request: Request, db: Session = Depends(get_db)):
    """Maschine bearbeiten"""
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")
    
    return templates.TemplateResponse("machines/form.html", {
        "request": request,
        "machine": machine,
        "title": "Maschine bearbeiten"
    })


@app.post("/machines/{machine_id}/update")
async def update_machine(
    machine_id: int,
    request: Request,
    name: str = Form(...),
    machine_type: str = Form(...),
    description: str = Form(""),
    depreciation_euro: str = Form("0"),
    lifespan_hours: str = Form("1"),
    power_kw: str = Form("0"),
    lifespan_pages: str = Form(""),
    depreciation_per_page: str = Form(""),
    cost_per_sheet: str = Form(""),
    db: Session = Depends(get_db)
):
    """Maschine aktualisieren"""
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")
    
    machine.name = name
    machine.machine_type = machine_type
    machine.description = description
    machine.depreciation_euro = parse_decimal(depreciation_euro)
    machine.lifespan_hours = parse_decimal(lifespan_hours) or 1
    machine.power_kw = parse_decimal(power_kw)
    machine.lifespan_pages = parse_decimal(lifespan_pages) if lifespan_pages else None
    machine.depreciation_per_page = parse_decimal(depreciation_per_page) if depreciation_per_page else None
    machine.cost_per_sheet = parse_decimal(cost_per_sheet) if cost_per_sheet else None
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


# =============================================================================
# PRODUKT ROUTES
# =============================================================================

@app.get("/products", response_class=HTMLResponse)
async def list_products(
    request: Request,
    product_type: str = "",
    market_filter: str = "",
    search: str = "",
    sort_by: str = "name",
    sort_order: str = "asc",
    db: Session = Depends(get_db)
):
    """Liste aller Produkte"""
    query = db.query(Product)
    
    if product_type:
        query = query.filter(Product.product_type == product_type)
    if market_filter == "market":
        query = query.filter(Product.is_for_market == 1)
    elif market_filter == "non_market":
        query = query.filter(Product.is_for_market == 0)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    
    # DB-Sortierung für Datenbankfelder
    if sort_by == "name":
        query = query.order_by(Product.name.desc() if sort_order == "desc" else Product.name.asc())
    elif sort_by == "type":
        query = query.order_by(Product.product_type.desc() if sort_order == "desc" else Product.product_type.asc())
    elif sort_by == "updated_at":
        query = query.order_by(Product.updated_at.asc() if sort_order == "asc" else Product.updated_at.desc())
    else:
        query = query.order_by(Product.name.asc())
    
    products = query.all()
    
    # Berechne Kosten für jedes Produkt
    products_with_costs = []
    for p in products:
        calc = p.calculate_costs()
        products_with_costs.append({
            'product': p,
            'costs': calc
        })
    
    # Python-seitige Sortierung für berechnete Felder
    if sort_by == "purchase_price":
        products_with_costs.sort(
            key=lambda x: float(x['costs'].get('purchase_price', 0) or 0),
            reverse=(sort_order == "desc")
        )
    elif sort_by == "selling_price":
        products_with_costs.sort(
            key=lambda x: float(x['costs'].get('selling_price', 0) or 0),
            reverse=(sort_order == "desc")
        )
    
    return templates.TemplateResponse("products/list.html", {
        "request": request,
        "products": products_with_costs,
        "product_type": product_type,
        "product_types": PRODUCT_TYPES,
        "market_filter": market_filter,
        "search": search,
        "sort_by": sort_by,
        "sort_order": sort_order
    })


@app.post("/products/{product_id}/toggle-market")
async def toggle_product_market_status(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Flohmarkt-Status eines Produkts umschalten"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
        
    product.is_for_market = 0 if product.is_for_market == 1 else 1
    product.updated_at = datetime.utcnow()
    db.commit()
    
    if request.headers.get("hx-request"):
        return Response(status_code=204)
    return RedirectResponse(url=request.headers.get("referer", "/products"), status_code=303)


@app.get("/products/new", response_class=HTMLResponse)
async def new_product_type_select(request: Request):
    """Produkttyp-Auswahl für neues Produkt"""
    return templates.TemplateResponse("products/product_type_select.html", {
        "request": request,
        "product_types": PRODUCT_TYPES,
        "title": "Neues Produkt"
    })


# ===== 3D-DRUCK ROUTES =====

@app.get("/products/3d-print/new", response_class=HTMLResponse)
async def new_3d_print_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neues 3D-Druck Produkt"""
    filaments = db.query(Material).filter(Material.material_type == "filament").order_by(Material.name).all()
    machines = db.query(Machine).filter(Machine.machine_type == "3d_printer").order_by(Machine.name).all()
    all_products = db.query(Product).order_by(Product.name).all()
    
    return templates.TemplateResponse("products/form_3d_print.html", {
        "request": request,
        "product": None,
        "categories": CATEGORIES,
        "filaments": filaments,
        "machines": machines,
        "all_products": all_products,
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
    is_for_market: str = Form("1"),
    notes: str = Form(""),
    # Komponenten
    component_name: list[str] = Form([]),
    component_quantity: list[str] = Form([]),
    component_unit_cost: list[str] = Form([]),
    component_notes: list[str] = Form([]),
    component_linked_product_id: list[str] = Form([]),
    db: Session = Depends(get_db)
):
    """Neues 3D-Druck Produkt erstellen"""
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
        is_for_market=1 if is_for_market in ["1", "true", "on"] else 0,
        notes=notes
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Komponenten erstellen
    for i in range(len(component_name)):
        if i < len(component_name) and component_name[i].strip():
            linked_id = None
            unit_cost = parse_decimal(component_unit_cost[i]) if i < len(component_unit_cost) else 0
            
            if i < len(component_linked_product_id) and component_linked_product_id[i]:
                try:
                    linked_id = int(component_linked_product_id[i])
                    linked_product = db.query(Product).filter(Product.id == linked_id).first()
                    if linked_product:
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


# ===== STICKER PRODUKTE =====

@app.get("/products/sticker/new", response_class=HTMLResponse)
async def new_sticker_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neues Sticker Produkt"""
    materials = db.query(Material).order_by(Material.name).all()
    machines = db.query(Machine).order_by(Machine.name).all()
    all_products = db.query(Product).order_by(Product.name).all()
    
    return templates.TemplateResponse("products/form_sticker.html", {
        "request": request,
        "product": None,
        "categories": CATEGORIES,
        "sticker_categories": STICKER_CATEGORIES,
        "materials": materials,
        "machines": machines,
        "all_products": all_products,
        "title": "Neues Sticker-Produkt"
    })


@app.post("/products/sticker")
async def create_sticker(
    request: Request,
    name: str = Form(...),
    category: str = Form("StickerSheet"),
    sheet_material_id: int = Form(...),
    sheet_count: str = Form("1"),
    units_per_sheet: str = Form("3"),
    units_per_batch: str = Form("3"),
    calculation_mode: str = Form("per_unit"),
    machine_ids: list[int] = Form([]),
    labor_minutes: str = Form("0"),
    labor_rate_per_hour: str = Form("20.00"),
    packaging_cost: str = Form("0"),
    shipping_cost: str = Form("0"),
    is_for_market: str = Form("1"),
    notes: str = Form(""),
    # Komponenten
    component_name: list[str] = Form([]),
    component_quantity: list[str] = Form([]),
    component_unit_cost: list[str] = Form([]),
    component_notes: list[str] = Form([]),
    component_linked_product_id: list[str] = Form([]),
    db: Session = Depends(get_db)
):
    """Neues Sticker Produkt erstellen"""
    primary_machine_id = machine_ids[0] if machine_ids else None
    additional_ids = ",".join(str(mid) for mid in machine_ids[1:]) if len(machine_ids) > 1 else None
    
    product = Product(
        name=name,
        product_type="sticker",
        category=category,
        sheet_material_id=sheet_material_id,
        sheet_count=parse_decimal(sheet_count) if sheet_count else 1,
        units_per_sheet=parse_decimal(units_per_sheet) if calculation_mode == "per_unit" else 1,
        units_per_batch=int(units_per_batch) if calculation_mode == "per_batch" else 1,
        calculation_mode=calculation_mode,
        machine_id=primary_machine_id,
        additional_machine_ids=additional_ids,
        labor_minutes=parse_decimal(labor_minutes),
        labor_rate_per_hour=parse_decimal(labor_rate_per_hour),
        packaging_cost=parse_decimal(packaging_cost),
        shipping_cost=parse_decimal(shipping_cost),
        is_for_market=1 if is_for_market in ["1", "true", "on"] else 0,
        notes=notes
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Komponenten erstellen
    for i in range(len(component_name)):
        if i < len(component_name) and component_name[i].strip():
            linked_id = None
            unit_cost = parse_decimal(component_unit_cost[i]) if i < len(component_unit_cost) else 0
            
            if i < len(component_linked_product_id) and component_linked_product_id[i]:
                try:
                    linked_id = int(component_linked_product_id[i])
                    linked_product = db.query(Product).filter(Product.id == linked_id).first()
                    if linked_product:
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
    
    # Lade Materialien je nach Typ
    filaments = []
    sticker_sheets = []
    if product.product_type == "3d_print":
        filaments = db.query(Material).filter(Material.material_type == "filament").order_by(Material.name).all()
    elif product.product_type == "sticker":
        sticker_sheets = db.query(Material).filter(Material.material_type == "sticker_sheet").order_by(Material.name).all()
    
    return templates.TemplateResponse("products/detail.html", {
        "request": request,
        "product": product,
        "calc": calculations,
        "filaments": filaments,
        "sticker_sheets": sticker_sheets,
        "success_msg": success,
        "error_msg": error
    })


@app.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def edit_product_form(product_id: int, request: Request, db: Session = Depends(get_db)):
    """Produkt bearbeiten - typ-spezifisches Formular"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    
    all_materials = db.query(Material).order_by(Material.name).all()
    machines = db.query(Machine).order_by(Machine.name).all()
    all_products = db.query(Product).filter(Product.id != product_id).order_by(Product.name).all()
    
    if product.product_type == "3d_print":
        filaments = db.query(Material).filter(Material.material_type == "filament").order_by(Material.name).all()
        template = "products/form_3d_print.html"
        return templates.TemplateResponse(template, {
            "request": request,
            "product": product,
            "categories": CATEGORIES,
            "filaments": filaments,
            "machines": machines,
            "all_products": all_products,
            "title": "Produkt bearbeiten"
        })
    elif product.product_type == "sticker":
        template = "products/form_sticker.html"
        return templates.TemplateResponse(template, {
            "request": request,
            "product": product,
            "categories": CATEGORIES,
            "sticker_categories": STICKER_CATEGORIES,
            "materials": all_materials,
            "machines": machines,
            "all_products": all_products,
            "title": "Sticker-Produkt bearbeiten"
        })
    else:
        # Fallback für alte Produkttypen
        template = "products/form_3d_print.html"
        return templates.TemplateResponse(template, {
            "request": request,
            "product": product,
            "categories": CATEGORIES,
            "filaments": all_materials,
            "machines": machines,
            "all_products": all_products,
            "title": "Produkt bearbeiten"
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
    sheet_count: str = Form("1"),
    units_per_sheet: str = Form("1"),
    units_per_batch: str = Form("1"),
    calculation_mode: str = Form("per_unit"),
    cut_time_hours: str = Form("0"),
    # Gemeinsame Felder
    machine_id: int = Form(None),
    labor_minutes: str = Form("0"),
    labor_rate_per_hour: str = Form("20.00"),
    packaging_cost: str = Form("0"),
    shipping_cost: str = Form("0"),
    is_for_market: str = Form(None),
    notes: str = Form(""),
    # Mehrere Maschinen (für Sticker)
    machine_ids: list[int] = Form([]),
    # Komponenten
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
    product.is_for_market = 1 if is_for_market in ["1", "true", "on"] else 0
    
    # Typ-spezifische Felder
    if product.product_type == "3d_print":
        product.filament_material_id = filament_material_id
        product.filament_weight_g = parse_decimal(filament_weight_g) if filament_weight_g else None
        product.print_time_hours = parse_decimal(print_time_hours)
        product.machine_id = machine_id
    elif product.product_type == "sticker":
        product.sheet_material_id = sheet_material_id
        product.sheet_count = parse_decimal(sheet_count) if sheet_count else 1
        product.calculation_mode = calculation_mode
        if calculation_mode == "per_unit":
            product.units_per_sheet = parse_decimal(units_per_sheet)
            product.units_per_batch = 1
        else:
            product.units_per_batch = int(units_per_batch)
            product.units_per_sheet = 1
        product.machine_id = machine_ids[0] if machine_ids else None
        product.additional_machine_ids = ",".join(str(mid) for mid in machine_ids[1:]) if len(machine_ids) > 1 else None
    
    # Gemeinsame Felder
    product.labor_minutes = parse_decimal(labor_minutes)
    product.labor_rate_per_hour = parse_decimal(labor_rate_per_hour)
    product.packaging_cost = parse_decimal(packaging_cost)
    product.shipping_cost = parse_decimal(shipping_cost)
    product.notes = notes
    product.updated_at = datetime.utcnow()
    
    # Komponenten aktualisieren (löschen und neu erstellen)
    db.query(ProductComponent).filter(ProductComponent.product_id == product_id).delete()
    
    for i in range(len(component_name)):
        if i < len(component_name) and component_name[i].strip():
            linked_id = None
            unit_cost = parse_decimal(component_unit_cost[i]) if i < len(component_unit_cost) else 0
            
            if i < len(component_linked_product_id) and component_linked_product_id[i]:
                try:
                    linked_id = int(component_linked_product_id[i])
                    linked_product = db.query(Product).filter(Product.id == linked_id).first()
                    if linked_product:
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
    return RedirectResponse(url=f"/products/{product_id}", status_code=303)


@app.post("/products/{product_id}/delete")
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Produkt löschen"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    
    # Lösche zuerst alle Komponenten
    db.query(ProductComponent).filter(ProductComponent.product_id == product_id).delete()
    
    db.delete(product)
    db.commit()
    
    return RedirectResponse(url="/products", status_code=303)


# =============================================================================
# API ROUTES
# =============================================================================

@app.get("/api/products/search")
async def api_search_products(q: str = "", db: Session = Depends(get_db)):
    """API: Produkte suchen (für Autocomplete)"""
    query = db.query(Product)
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    products = query.order_by(Product.name).limit(20).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "product_type": p.product_type,
            "cost": p.calculate_costs()["total_cost"]
        }
        for p in products
    ]


@app.get("/api/products/{product_id}/details")
async def api_product_details(product_id: int, db: Session = Depends(get_db)):
    """API: Produktdetails für Verknüpfung"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    
    calc = product.calculate_costs()
    return {
        "id": product.id,
        "name": product.name,
        "product_type": product.product_type,
        "total_cost": calc["total_cost"]
    }



# ===== FEEDBACK & IDEEN =====

@app.get("/feedback-ideas", response_class=HTMLResponse)
async def list_feedback_ideas(
    request: Request,
    status_filter: str = "",
    search: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db)
):
    """Liste aller Feedback-Eintraege und Ideen"""
    query = db.query(FeedbackIdea)
    
    if status_filter:
        query = query.filter(FeedbackIdea.status == status_filter)
    if search:
        query = query.filter(FeedbackIdea.description.ilike(f"%{search}%"))
    
    sort_col = FeedbackIdea.created_at
    if sort_by == "updated_at":
        sort_col = FeedbackIdea.updated_at
    elif sort_by == "status":
        sort_col = FeedbackIdea.status
    
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())
    
    items = query.all()
    open_count = db.query(FeedbackIdea).filter(FeedbackIdea.status == 'open').count()
    done_count = db.query(FeedbackIdea).filter(FeedbackIdea.status == 'done').count()
    
    return templates.TemplateResponse("feedback_ideas/list.html", {
        "request": request,
        "items": items,
        "status_filter": status_filter,
        "open_count": open_count,
        "done_count": done_count,
        "search": search,
        "sort_by": sort_by,
        "sort_order": sort_order
    })


@app.get("/feedback-ideas/new", response_class=HTMLResponse)
async def new_feedback_idea_form(request: Request):
    """Formular für neues Feedback / neue Idee"""
    return templates.TemplateResponse("feedback_ideas/form.html", {
        "request": request,
        "item": None,
        "title": "Neues Feedback / Idee"
    })


@app.post("/feedback-ideas")
async def create_feedback_idea(
    request: Request,
    description: str = Form(...),
    db: Session = Depends(get_db)
):
    """Neues Feedback oder Idee erstellen"""
    item = FeedbackIdea(
        description=description.strip(),
        status='open'
    )
    db.add(item)
    db.commit()
    return RedirectResponse(url="/feedback-ideas", status_code=303)


@app.get("/feedback-ideas/{item_id}/edit", response_class=HTMLResponse)
async def edit_feedback_idea_form(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Formular zum Bearbeiten"""
    item = db.query(FeedbackIdea).filter(FeedbackIdea.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    
    return templates.TemplateResponse("feedback_ideas/form.html", {
        "request": request,
        "item": item,
        "title": "Feedback / Idee bearbeiten"
    })


@app.post("/feedback-ideas/{item_id}/update")
async def update_feedback_idea(
    item_id: int,
    request: Request,
    description: str = Form(...),
    db: Session = Depends(get_db)
):
    """Feedback/Idee aktualisieren"""
    item = db.query(FeedbackIdea).filter(FeedbackIdea.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    
    item.description = description.strip()
    item.updated_at = datetime.utcnow()
    
    db.commit()
    return RedirectResponse(url="/feedback-ideas", status_code=303)


@app.post("/feedback-ideas/{item_id}/status")
async def toggle_feedback_idea_status(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Status toggeln (open <-> done)"""
    item = db.query(FeedbackIdea).filter(FeedbackIdea.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    
    item.status = 'done' if item.status == 'open' else 'open'
    item.updated_at = datetime.utcnow()
    db.commit()
    
    return RedirectResponse(url="/feedback-ideas", status_code=303)


@app.post("/feedback-ideas/{item_id}/delete")
async def delete_feedback_idea(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Feedback/Idee löschen"""
    item = db.query(FeedbackIdea).filter(FeedbackIdea.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    
    db.delete(item)
    db.commit()
    return RedirectResponse(url="/feedback-ideas", status_code=303)


# =============================================================================
# FLOHMARKT & EVENT-VORPRODUKTION ROUTES
# =============================================================================

DEFAULT_PACKLIST = [
    ("Stand & Aufbau", "Pavillon / Zelt & Gewichte einpacken"),
    ("Stand & Aufbau", "Verkaufstisch(e) & Klappstühle"),
    ("Stand & Aufbau", "Tischdecke(n) & Stand-Deko"),
    ("Stand & Aufbau", "Warenträger & Produktaufsteller"),
    ("Kasse & Finanzen", "Geldkassette & ausreichend Wechselgeld"),
    ("Kasse & Finanzen", "Kartenzahlungsgerät (SumUp etc.) geladen"),
    ("Kasse & Finanzen", "Taschenrechner & Quittungsblock"),
    ("Verkauf & Marketing", "Preisschilder & Aufsteller"),
    ("Verkauf & Marketing", "Papiertragetaschen & Verpackungsbeutel"),
    ("Verkauf & Marketing", "Visitenkarten & Flyer"),
    ("Allgemein & Notfall", "Klebeband, Schere & Kabelbinder"),
    ("Allgemein & Notfall", "Stifte, Filzstift & Notizblock"),
    ("Allgemein & Notfall", "Powerbank & Smartphone-Ladekabel"),
    ("Allgemein & Notfall", "Müllbeutel & Putztücher"),
    ("Allgemein & Notfall", "Getränke & Snacks für den Tag"),
]


@app.get("/events", response_class=HTMLResponse)
async def list_events(
    request: Request,
    status_filter: str = "",
    search: str = "",
    sort_by: str = "event_date",
    sort_order: str = "asc",
    db: Session = Depends(get_db)
):
    """Übersicht aller Flohmärkte und Events"""
    query = db.query(MarketEvent)
    
    if status_filter == "active":
        query = query.filter(MarketEvent.status.in_(["planning", "in_production", "ready"]))
    elif status_filter == "completed":
        query = query.filter(MarketEvent.status.in_(["completed", "archived"]))
    elif status_filter:
        query = query.filter(MarketEvent.status == status_filter)
        
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (MarketEvent.name.ilike(search_pattern)) |
            (MarketEvent.location.ilike(search_pattern)) |
            (MarketEvent.description.ilike(search_pattern))
        )
        
    if sort_by == "name":
        order_col = MarketEvent.name
    elif sort_by == "created_at":
        order_col = MarketEvent.created_at
    else:  # event_date
        order_col = MarketEvent.event_date
        
    if sort_order == "desc":
        query = query.order_by(order_col.desc().nullslast(), MarketEvent.created_at.desc())
    else:
        query = query.order_by(order_col.asc().nullslast(), MarketEvent.created_at.asc())
        
    events = query.all()
    
    total_count = db.query(MarketEvent).count()
    active_count = db.query(MarketEvent).filter(MarketEvent.status.in_(["planning", "in_production", "ready"])).count()
    completed_count = db.query(MarketEvent).filter(MarketEvent.status.in_(["completed", "archived"])).count()
    
    return templates.TemplateResponse("events/list.html", {
        "request": request,
        "events": events,
        "total_count": total_count,
        "active_count": active_count,
        "completed_count": completed_count,
        "status_filter": status_filter,
        "search": search,
        "sort_by": sort_by,
        "sort_order": sort_order
    })


@app.get("/events/new", response_class=HTMLResponse)
async def new_event_form(request: Request):
    """Neues Event anlegen Formular"""
    return templates.TemplateResponse("events/form.html", {
        "request": request,
        "event": None,
        "is_edit": False
    })


@app.post("/events/new")
async def create_event(
    request: Request,
    name: str = Form(...),
    event_date: str = Form(None),
    location: str = Form(None),
    description: str = Form(None),
    status: str = Form("planning"),
    load_default_packlist: str = Form(None),
    db: Session = Depends(get_db)
):
    """Neues Event speichern"""
    parsed_date = None
    if event_date and event_date.strip():
        try:
            parsed_date = datetime.strptime(event_date.strip(), "%Y-%m-%d")
        except ValueError:
            pass
            
    event = MarketEvent(
        name=name.strip(),
        event_date=parsed_date,
        location=location.strip() if location else None,
        description=description.strip() if description else None,
        status=status
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    
    # Standard-Packliste hinzufügen falls gewünscht
    if load_default_packlist in ["true", "on", "1"]:
        for idx, (cat, title) in enumerate(DEFAULT_PACKLIST):
            todo = EventTodo(
                event_id=event.id,
                title=title,
                category=cat,
                is_done=0,
                sort_order=idx
            )
            db.add(todo)
        db.commit()
        
    return RedirectResponse(url=f"/events/{event.id}", status_code=303)


@app.get("/events/{event_id}", response_class=HTMLResponse)
async def event_detail(event_id: int, request: Request, db: Session = Depends(get_db)):
    """Detailansicht & Dashboard für ein einzelnes Event"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    totals = event.calculate_totals()
    market_products = db.query(Product).filter(Product.is_for_market == 1).order_by(Product.name.asc()).all()
    all_products = db.query(Product).order_by(Product.name.asc()).all()
    
    # ToDos nach Kategorien gruppieren
    todos_by_category = {}
    for todo in event.todos:
        cat = todo.category or "Allgemein"
        if cat not in todos_by_category:
            todos_by_category[cat] = []
        todos_by_category[cat].append(todo)
        
    return templates.TemplateResponse("events/detail.html", {
        "request": request,
        "event": event,
        "totals": totals,
        "market_products": market_products,
        "all_products": all_products,
        "todos_by_category": todos_by_category
    })


@app.get("/events/{event_id}/edit", response_class=HTMLResponse)
async def edit_event_form(event_id: int, request: Request, db: Session = Depends(get_db)):
    """Event bearbeiten Formular"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    return templates.TemplateResponse("events/form.html", {
        "request": request,
        "event": event,
        "is_edit": True
    })


@app.post("/events/{event_id}/update")
async def update_event(
    event_id: int,
    request: Request,
    name: str = Form(...),
    event_date: str = Form(None),
    location: str = Form(None),
    description: str = Form(None),
    status: str = Form("planning"),
    db: Session = Depends(get_db)
):
    """Event aktualisieren"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    parsed_date = None
    if event_date and event_date.strip():
        try:
            parsed_date = datetime.strptime(event_date.strip(), "%Y-%m-%d")
        except ValueError:
            pass
            
    event.name = name.strip()
    event.event_date = parsed_date
    event.location = location.strip() if location else None
    event.description = description.strip() if description else None
    event.status = status
    event.updated_at = datetime.utcnow()
    
    db.commit()
    return RedirectResponse(url=f"/events/{event.id}", status_code=303)


@app.post("/events/{event_id}/status")
async def update_event_status(
    event_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    """Event-Status schnell ändern"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    event.status = status
    event.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"/events/{event.id}", status_code=303)


@app.post("/events/{event_id}/delete")
async def delete_event(event_id: int, db: Session = Depends(get_db)):
    """Event löschen"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    db.delete(event)
    db.commit()
    return RedirectResponse(url="/events", status_code=303)


@app.post("/events/{event_id}/items/add")
async def add_event_item(
    event_id: int,
    product_id: int = Form(None),
    target_quantity: int = Form(1),
    notes: str = Form(None),
    db: Session = Depends(get_db)
):
    """Produkt zur Vorproduktionsliste hinzufügen"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    # Prüfen ob Artikel bereits vorhanden -> dann Soll-Menge erhöhen
    existing_item = db.query(EventItem).filter(
        EventItem.event_id == event_id,
        EventItem.product_id == product_id
    ).first() if product_id else None
    
    if existing_item:
        existing_item.target_quantity += max(1, target_quantity)
        if notes and notes.strip():
            if existing_item.notes:
                existing_item.notes += f", {notes.strip()}"
            else:
                existing_item.notes = notes.strip()
    else:
        new_item = EventItem(
            event_id=event_id,
            product_id=product_id if product_id else None,
            target_quantity=max(1, target_quantity),
            produced_quantity=0,
            notes=notes.strip() if notes else None
        )
        db.add(new_item)
        
    db.commit()
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@app.post("/events/{event_id}/items/{item_id}/adjust")
async def adjust_event_item_quantity(
    event_id: int,
    item_id: int,
    delta: int = Form(None),
    produced_quantity: int = Form(None),
    target_quantity: int = Form(None),
    db: Session = Depends(get_db)
):
    """Gefertigte oder Soll-Menge eines Artikels anpassen"""
    item = db.query(EventItem).filter(EventItem.id == item_id, EventItem.event_id == event_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
        
    if delta is not None:
        item.produced_quantity = max(0, item.produced_quantity + delta)
    elif produced_quantity is not None:
        item.produced_quantity = max(0, produced_quantity)
        
    if target_quantity is not None and target_quantity > 0:
        item.target_quantity = target_quantity
        
    item.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@app.post("/events/{event_id}/items/{item_id}/delete")
async def delete_event_item(event_id: int, item_id: int, db: Session = Depends(get_db)):
    """Artikel aus Vorproduktion löschen"""
    item = db.query(EventItem).filter(EventItem.id == item_id, EventItem.event_id == event_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
        
    db.delete(item)
    db.commit()
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@app.post("/events/{event_id}/todos/add")
async def add_event_todo(
    event_id: int,
    title: str = Form(...),
    category: str = Form("Allgemein"),
    db: Session = Depends(get_db)
):
    """ToDo / Packlisten-Eintrag hinzufügen"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    todo = EventTodo(
        event_id=event_id,
        title=title.strip(),
        category=category.strip() if category else "Allgemein",
        is_done=0
    )
    db.add(todo)
    db.commit()
    return RedirectResponse(url=f"/events/{event_id}#todos", status_code=303)


@app.post("/events/{event_id}/todos/{todo_id}/toggle")
async def toggle_event_todo(
    event_id: int,
    todo_id: int,
    db: Session = Depends(get_db)
):
    """ToDo Status umschalten"""
    todo = db.query(EventTodo).filter(EventTodo.id == todo_id, EventTodo.event_id == event_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="ToDo nicht gefunden")
        
    todo.is_done = 1 if todo.is_done == 0 else 0
    todo.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"/events/{event_id}#todos", status_code=303)


@app.post("/events/{event_id}/todos/{todo_id}/delete")
async def delete_event_todo(
    event_id: int,
    todo_id: int,
    db: Session = Depends(get_db)
):
    """ToDo löschen"""
    todo = db.query(EventTodo).filter(EventTodo.id == todo_id, EventTodo.event_id == event_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="ToDo nicht gefunden")
        
    db.delete(todo)
    db.commit()
    return RedirectResponse(url=f"/events/{event_id}#todos", status_code=303)


@app.post("/events/{event_id}/todos/load-template")
async def load_event_todo_template(
    event_id: int,
    db: Session = Depends(get_db)
):
    """Standard-Packliste laden (vermeidet Duplikate)"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    existing_titles = {t.title for t in event.todos}
    
    for idx, (cat, title) in enumerate(DEFAULT_PACKLIST):
        if title not in existing_titles:
            todo = EventTodo(
                event_id=event.id,
                title=title,
                category=cat,
                is_done=0,
                sort_order=len(existing_titles) + idx
            )
            db.add(todo)
            
    db.commit()
    return RedirectResponse(url=f"/events/{event_id}#todos", status_code=303)


@app.get("/events/{event_id}/print", response_class=HTMLResponse)
async def print_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Druckansicht für ein Event"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    totals = event.calculate_totals()
    
    todos_by_category = {}
    for todo in event.todos:
        cat = todo.category or "Allgemein"
        if cat not in todos_by_category:
            todos_by_category[cat] = []
        todos_by_category[cat].append(todo)
        
    return templates.TemplateResponse("events/print.html", {
        "request": request,
        "event": event,
        "totals": totals,
        "todos_by_category": todos_by_category,
        "now": datetime.utcnow()
    })


# ========================================
# TOOLS - PNG TO SVG CONVERTER
# ========================================

# Verzeichnis fuer temporaere Uploads
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
    
    # Pruefe Dateityp
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
        
        # Berechne Dateigroessen
        original_size = len(content)
        svg_size = len(svg_content.encode('utf-8'))
        
        # Wenn speichern aktiviert, in permanenten Speicher verschieben
        db_entry = None
        if save_file == "true":
            # Erstelle Unterordner basierend auf Datum fuer bessere Organisation
            date_folder = datetime.now().strftime("%Y/%m")
            storage_subdir = FILE_STORAGE_PATH / date_folder
            storage_subdir.mkdir(parents=True, exist_ok=True)
            
            # Permanente Pfade
            png_filename = f"{file_id}.png"
            svg_filename = f"{file_id}.svg"
            png_path = storage_subdir / png_filename
            svg_path = storage_subdir / svg_filename
            
            # Kopiere Dateien in permanenten Speicher
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
        
        # Loesche temporaere Dateien
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

@app.post("/tools/png-to-svg/download")
async def download_fresh_svg(
    request: Request,
    svg_content: str = Form(...),
    filename: str = Form(...)
):
    """Download einer frisch konvertierten SVG-Datei"""
    safe_filename = filename.rsplit('.', 1)[0] + ".svg"
    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'}
    )

@app.get("/tools/converted-files", response_class=HTMLResponse)
async def list_converted_files(
    request: Request,
    search: str = "",
    sort_by: str = "original_filename",
    sort_order: str = "asc",
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
    
    sort_col = ConvertedFile.original_filename
    if sort_by == "created_at":
        sort_col = ConvertedFile.created_at
    elif sort_by == "size_reduction":
        sort_col = ConvertedFile.svg_size_bytes
    
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())
    
    files = query.all()
    
    return templates.TemplateResponse("tools/converted_files_list.html", {
        "request": request,
        "title": "Gespeicherte Konvertierungen",
        "files": files,
        "search": search,
        "sort_by": sort_by,
        "sort_order": sort_order
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
    """Loesche eine gespeicherte Konvertierung"""
    file_entry = db.query(ConvertedFile).filter(ConvertedFile.id == file_id).first()
    if not file_entry:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    # Loesche physische Dateien
    png_path = FILE_STORAGE_PATH / file_entry.file_path_png
    svg_path = FILE_STORAGE_PATH / file_entry.file_path_svg
    
    png_path.unlink(missing_ok=True)
    svg_path.unlink(missing_ok=True)
    
    # Loesche DB-Eintrag
    db.delete(file_entry)
    db.commit()
    
    return RedirectResponse(url="/tools/converted-files", status_code=303)
