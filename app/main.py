from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from database import engine, get_db
from models import Base, Product, Material, Machine, STROM_PREIS_KWH
from datetime import datetime
import time

# Wait for database and create tables
max_retries = 30
retry_delay = 2

for i in range(max_retries):
    try:
        Base.metadata.create_all(bind=engine)
        print("Database connected and tables created successfully!")
        break
    except OperationalError as e:
        print(f"Database not ready yet (attempt {i+1}/{max_retries}). Retrying in {retry_delay} seconds...")
        time.sleep(retry_delay)
else:
    print("Could not connect to database after maximum retries!")
    raise Exception("Database connection failed")

app = FastAPI(title="Produkt Kalkulator")

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

# Materialtypen
MATERIAL_TYPES = [
    ("filament", "3D-Filament (€/kg)"),
    ("sticker_sheet", "Stickerbogen (€/Bogen)"),
    ("diecut_sticker", "DieCut-Sticker Material"),
    ("paper", "Papier"),
    ("other", "Sonstiges")
]

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
    
    return templates.TemplateResponse("materials/list.html", {
        "request": request,
        "materials": materials,
        "material_type": material_type,
        "material_types": MATERIAL_TYPES
    })

@app.get("/materials/new", response_class=HTMLResponse)
async def new_material_form(request: Request):
    """Formular für neues Material"""
    return templates.TemplateResponse("materials/form.html", {
        "request": request,
        "material": None,
        "material_types": MATERIAL_TYPES,
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
    
    return templates.TemplateResponse("materials/form.html", {
        "request": request,
        "material": material,
        "material_types": MATERIAL_TYPES,
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
    if product.product_type == "3d_print":
        filaments = db.query(Material).filter(Material.material_type == "filament").order_by(Material.name).all()
    elif product.product_type == "sticker_sheet":
        sticker_sheets = db.query(Material).filter(Material.material_type == "sticker_sheet").order_by(Material.name).all()
    
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
    
    # Lade entsprechende Maschinen (nur für 3D-Druck)
    machines = []
    if product.product_type == "3d_print":
        machines = db.query(Machine).filter(Machine.machine_type == "3d_printer").order_by(Machine.name).all()
    
    # Wähle das richtige Template je nach Produkttyp
    if product.product_type == "3d_print":
        template = "products/form_3d_print.html"
    elif product.product_type == "sticker_sheet":
        template = "products/form_sticker_sheet.html"
    else:
        template = "products/form_generic.html"
    
    return templates.TemplateResponse(template, {
        "request": request,
        "product": product,
        "categories": CATEGORIES,
        "filaments": filaments,
        "sticker_sheets": sticker_sheets,
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
    cut_time_hours: float = Form(0),
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
    elif product.product_type == "sticker_sheet":
        product.sheet_material_id = sheet_material_id
        product.sheet_count = sheet_count
        product.cut_time_hours = cut_time_hours
    
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
