from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from database import engine, get_db, SessionLocal
from models import Base, Product, Material, MaterialType, Machine, Feedback, Idea, STROM_PREIS_KWH
from datetime import datetime
import time


def seed_material_types(db: Session):
    """Initialisiert Standard-Materialtypen falls noch keine existieren"""
    existing = db.query(MaterialType).first()
    if existing:
        return  # Bereits initialisiert
    
    default_types = [
        ("filament", "3D-Filament (€/kg)", "Filament für 3D-Drucker", 1),
        ("sticker_sheet", "Stickerbogen (€/Bogen)", "Bögen für Sticker", 2),
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
    ("sticker_sheet", "Stickerbogen"),
    ("diecut_sticker", "DieCut-Sticker"),
    ("paper", "Papierprodukt"),
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
        "machine_types": [("3d_printer", "3D-Drucker"), ("cutter_plotter", "Cutter/Plotter"), ("other", "Sonstiges")]
    })

@app.get("/machines/new", response_class=HTMLResponse)
async def new_machine_form(request: Request):
    """Formular für neue Maschine"""
    return templates.TemplateResponse("machines/form.html", {
        "request": request,
        "machine": None,
        "machine_types": [("3d_printer", "3D-Drucker"), ("cutter_plotter", "Cutter/Plotter"), ("other", "Sonstiges")],
        "title": "Neue Maschine",
        "STROM_PREIS_KWH": STROM_PREIS_KWH
    })

@app.post("/machines")
async def create_machine(
    request: Request,
    name: str = Form(...),
    machine_type: str = Form(...),
    depreciation_euro: float = Form(...),
    lifespan_hours: float = Form(...),
    power_kw: float = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neue Maschine erstellen"""
    machine = Machine(
        name=name,
        machine_type=machine_type,
        depreciation_euro=depreciation_euro,
        lifespan_hours=lifespan_hours,
        power_kw=power_kw,
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
        "machine_types": [("3d_printer", "3D-Drucker"), ("cutter_plotter", "Cutter/Plotter"), ("other", "Sonstiges")],
        "title": "Maschine bearbeiten",
        "STROM_PREIS_KWH": STROM_PREIS_KWH
    })

@app.post("/machines/{machine_id}/update")
async def update_machine(
    machine_id: int,
    request: Request,
    name: str = Form(...),
    machine_type: str = Form(...),
    depreciation_euro: float = Form(...),
    lifespan_hours: float = Form(...),
    power_kw: float = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Maschine aktualisieren"""
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")
    
    machine.name = name
    machine.machine_type = machine_type
    machine.depreciation_euro = depreciation_euro
    machine.lifespan_hours = lifespan_hours
    machine.power_kw = power_kw
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
    query = db.query(Product)
    
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
    filament_weight_g: float = Form(...),
    print_time_hours: float = Form(0),
    machine_id: int = Form(...),
    labor_hours: float = Form(0),
    labor_rate_per_hour: float = Form(20.00),
    packaging_cost: float = Form(0),
    shipping_cost: float = Form(0),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neues 3D-Druck Produkt erstellen"""
    product = Product(
        name=name,
        product_type="3d_print",
        category=category,
        filament_material_id=filament_material_id,
        filament_weight_g=filament_weight_g,
        print_time_hours=print_time_hours,
        machine_id=machine_id,
        labor_hours=labor_hours,
        labor_rate_per_hour=labor_rate_per_hour,
        packaging_cost=packaging_cost,
        shipping_cost=shipping_cost,
        notes=notes
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return RedirectResponse(url=f"/products/{product.id}", status_code=303)

# ===== STICKER-BOGEN PRODUKTE =====

@app.get("/products/sticker-sheet/new", response_class=HTMLResponse)
async def new_sticker_sheet_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neues Stickerbogen Produkt"""
    sticker_sheets = db.query(Material).filter(Material.material_type == "sticker_sheet").order_by(Material.name).all()
    
    return templates.TemplateResponse("products/form_sticker_sheet.html", {
        "request": request,
        "product": None,
        "categories": CATEGORIES,
        "sticker_sheets": sticker_sheets,
        "title": "Neuer Stickerbogen"
    })

@app.post("/products/sticker-sheet")
async def create_sticker_sheet(
    request: Request,
    name: str = Form(...),
    category: str = Form("Sonstiges"),
    sheet_material_id: int = Form(...),
    sheet_count: float = Form(...),
    units_per_sheet: float = Form(3),  # Standard: 3 Bögen pro Material
    labor_hours: float = Form(0),
    labor_rate_per_hour: float = Form(20.00),
    packaging_cost: float = Form(0),
    shipping_cost: float = Form(0),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neues Stickerbogen Produkt erstellen"""
    product = Product(
        name=name,
        product_type="sticker_sheet",
        category=category,
        sheet_material_id=sheet_material_id,
        sheet_count=sheet_count,
        units_per_sheet=units_per_sheet,
        labor_hours=labor_hours,
        labor_rate_per_hour=labor_rate_per_hour,
        packaging_cost=packaging_cost,
        shipping_cost=shipping_cost,
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
    
    return templates.TemplateResponse("products/form_diecut_sticker.html", {
        "request": request,
        "product": None,
        "categories": CATEGORIES,
        "sticker_sheets": sticker_sheets,
        "title": "Neue DieCut Sticker"
    })

@app.post("/products/diecut-sticker")
async def create_diecut_sticker(
    request: Request,
    name: str = Form(...),
    category: str = Form("Sonstiges"),
    sheet_material_id: int = Form(...),
    sheet_count: float = Form(...),
    units_per_sheet: float = Form(6),  # Standard: 6 Sticker pro Bogen
    labor_hours: float = Form(0),
    labor_rate_per_hour: float = Form(20.00),
    packaging_cost: float = Form(0),
    shipping_cost: float = Form(0),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neue DieCut Sticker erstellen"""
    product = Product(
        name=name,
        product_type="diecut_sticker",
        category=category,
        sheet_material_id=sheet_material_id,
        sheet_count=sheet_count,
        units_per_sheet=units_per_sheet,
        labor_hours=labor_hours,
        labor_rate_per_hour=labor_rate_per_hour,
        packaging_cost=packaging_cost,
        shipping_cost=shipping_cost,
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
    laser1_power_percent: float = Form(80.0),
    laser1_speed_mm_s: float = Form(200),
    laser1_passes: int = Form(1),
    laser1_dpi: int = Form(300),
    laser1_lines_per_cm: int = Form(60),
    # Layer 2 (optional)
    laser2_type: str = Form(None),
    laser2_power_percent: float = Form(100.0),
    laser2_speed_mm_s: float = Form(100),
    laser2_passes: int = Form(1),
    laser2_dpi: int = Form(300),
    laser2_lines_per_cm: int = Form(60),
    # Layer 3 (optional)
    laser3_type: str = Form(None),
    laser3_power_percent: float = Form(50.0),
    laser3_speed_mm_s: float = Form(300),
    laser3_passes: int = Form(1),
    laser3_dpi: int = Form(600),
    laser3_lines_per_cm: int = Form(120),
    labor_hours: float = Form(0),
    labor_rate_per_hour: float = Form(20.00),
    packaging_cost: float = Form(0),
    shipping_cost: float = Form(0),
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
        laser1_power_percent=laser1_power_percent,
        laser1_speed_mm_s=laser1_speed_mm_s,
        laser1_passes=laser1_passes,
        laser1_dpi=laser1_dpi,
        laser1_lines_per_cm=laser1_lines_per_cm,
        # Layer 2
        laser2_type=laser2_type if laser2_type else None,
        laser2_power_percent=laser2_power_percent,
        laser2_speed_mm_s=laser2_speed_mm_s,
        laser2_passes=laser2_passes,
        laser2_dpi=laser2_dpi,
        laser2_lines_per_cm=laser2_lines_per_cm,
        # Layer 3
        laser3_type=laser3_type if laser3_type else None,
        laser3_power_percent=laser3_power_percent,
        laser3_speed_mm_s=laser3_speed_mm_s,
        laser3_passes=laser3_passes,
        laser3_dpi=laser3_dpi,
        laser3_lines_per_cm=laser3_lines_per_cm,
        labor_hours=labor_hours,
        labor_rate_per_hour=labor_rate_per_hour,
        packaging_cost=packaging_cost,
        shipping_cost=shipping_cost,
        notes=notes
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return RedirectResponse(url=f"/products/{product.id}", status_code=303)

# ===== PRODUKT ANZEIGEN/BEARBEITEN =====

@app.get("/products/{product_id}", response_class=HTMLResponse)
async def view_product(product_id: int, request: Request, db: Session = Depends(get_db)):
    """Produktdetails anzeigen"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    
    calculations = product.calculate_costs()
    
    # Lade Materialien je nach Typ
    filaments = []
    sticker_sheets = []
    laser_materials = []
    if product.product_type == "3d_print":
        filaments = db.query(Material).filter(Material.material_type == "filament").order_by(Material.name).all()
    elif product.product_type in ["sticker_sheet", "diecut_sticker"]:
        sticker_sheets = db.query(Material).filter(Material.material_type == "sticker_sheet").order_by(Material.name).all()
    elif product.product_type == "laser_engraving":
        laser_materials = db.query(Material).filter(Material.material_type == "laser_material").order_by(Material.name).all()
    
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
        "machines": machines
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
    
    # Lade entsprechende Maschinen (nur für 3D-Druck)
    machines = []
    if product.product_type == "3d_print":
        machines = db.query(Machine).filter(Machine.machine_type == "3d_printer").order_by(Machine.name).all()
    
    # Wähle das richtige Template je nach Produkttyp
    if product.product_type == "3d_print":
        template = "products/form_3d_print.html"
    elif product.product_type == "sticker_sheet":
        template = "products/form_sticker_sheet.html"
    elif product.product_type == "diecut_sticker":
        template = "products/form_diecut_sticker.html"
    elif product.product_type == "laser_engraving":
        template = "products/form_laser_engraving.html"
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
    filament_weight_g: float = Form(None),
    print_time_hours: float = Form(0),
    # Sticker Felder
    sheet_material_id: int = Form(None),
    sheet_count: float = Form(None),
    units_per_sheet: float = Form(1),
    cut_time_hours: float = Form(0),
    # Laser-Gravur Felder - Layer 1
    laser_material_id: int = Form(None),
    laser_design_name: str = Form(None),
    laser1_type: str = Form(None),
    laser1_power_percent: float = Form(80.0),
    laser1_speed_mm_s: float = Form(200),
    laser1_passes: int = Form(1),
    laser1_dpi: int = Form(300),
    laser1_lines_per_cm: int = Form(60),
    # Laser-Gravur Felder - Layer 2
    laser2_type: str = Form(None),
    laser2_power_percent: float = Form(100.0),
    laser2_speed_mm_s: float = Form(100),
    laser2_passes: int = Form(1),
    laser2_dpi: int = Form(300),
    laser2_lines_per_cm: int = Form(60),
    # Laser-Gravur Felder - Layer 3
    laser3_type: str = Form(None),
    laser3_power_percent: float = Form(50.0),
    laser3_speed_mm_s: float = Form(300),
    laser3_passes: int = Form(1),
    laser3_dpi: int = Form(600),
    laser3_lines_per_cm: int = Form(120),
    # Gemeinsame Felder
    machine_id: int = Form(None),
    labor_hours: float = Form(0),
    labor_rate_per_hour: float = Form(20.00),
    packaging_cost: float = Form(0),
    shipping_cost: float = Form(0),
    notes: str = Form(""),
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
        product.filament_weight_g = filament_weight_g
        product.print_time_hours = print_time_hours
    elif product.product_type in ["sticker_sheet", "diecut_sticker"]:
        product.sheet_material_id = sheet_material_id
        product.sheet_count = sheet_count
        product.units_per_sheet = units_per_sheet
        product.cut_time_hours = cut_time_hours
    elif product.product_type == "laser_engraving":
        product.laser_material_id = laser_material_id
        product.laser_design_name = laser_design_name
        # Layer 1
        product.laser1_type = laser1_type
        product.laser1_power_percent = laser1_power_percent
        product.laser1_speed_mm_s = laser1_speed_mm_s
        product.laser1_passes = laser1_passes
        product.laser1_dpi = laser1_dpi
        product.laser1_lines_per_cm = laser1_lines_per_cm
        # Layer 2
        product.laser2_type = laser2_type if laser2_type else None
        product.laser2_power_percent = laser2_power_percent
        product.laser2_speed_mm_s = laser2_speed_mm_s
        product.laser2_passes = laser2_passes
        product.laser2_dpi = laser2_dpi
        product.laser2_lines_per_cm = laser2_lines_per_cm
        # Layer 3
        product.laser3_type = laser3_type if laser3_type else None
        product.laser3_power_percent = laser3_power_percent
        product.laser3_speed_mm_s = laser3_speed_mm_s
        product.laser3_passes = laser3_passes
        product.laser3_dpi = laser3_dpi
        product.laser3_lines_per_cm = laser3_lines_per_cm
    
    # Gemeinsame Felder
    if product.product_type == "3d_print":
        product.machine_id = machine_id
    product.labor_hours = labor_hours
    product.labor_rate_per_hour = labor_rate_per_hour
    product.packaging_cost = packaging_cost
    product.shipping_cost = shipping_cost
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
