"""Materialien und Materialtypen."""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session, selectinload

from common import (
    bad_request, get_material_types, material_to_json, parse_money,
)
from core import templates
from database import get_db
from models import (
    Brand, Material, MaterialType, ProductMaterial, ProductPackaging,
)
from units import MATERIAL_UNITS, is_valid_unit

router = APIRouter()


def parse_material_form(db: Session, name, material_type_id, brand, color, unit, price_per_unit, description) -> dict:
    name = (name or "").strip()
    if not name:
        bad_request("Bitte einen Materialnamen angeben.")
    if not db.query(MaterialType).filter(MaterialType.id == material_type_id).first():
        bad_request("Unbekannter Materialtyp.")
    if not is_valid_unit(unit):
        bad_request("Unbekannte Einheit.")
    return {
        "name": name,
        "material_type_id": material_type_id,
        "brand_name": (brand or "").strip(),
        "color": (color or "").strip(),
        "unit": unit,
        "price": parse_money(price_per_unit, "Preis pro Einheit"),
        "description": description,
    }


def apply_material_form(db: Session, material: Material, values: dict) -> None:
    """Werte auf das Material übertragen: Marke wird bei Bedarf angelegt, ein geänderter Preis
    erzeugt einen neuen Eintrag in der Preis-Historie."""
    brand = None
    if values["brand_name"]:
        brand = db.query(Brand).filter(Brand.name == values["brand_name"]).first()
        if brand is None:
            brand = Brand(name=values["brand_name"])
            db.add(brand)
    material.name = values["name"]
    material.material_type_id = values["material_type_id"]
    material.brand = brand
    material.color = values["color"]
    material.unit = values["unit"]
    material.description = values["description"]
    material.set_price(values["price"])

@router.get("/materials", response_class=HTMLResponse)
async def list_materials(request: Request, error: str = "", db: Session = Depends(get_db)):
    """Liste aller Materialien; Sortieren und Filtern passiert im Browser (Spaltenköpfe)."""
    materials = (db.query(Material).options(selectinload(Material.brand), selectinload(Material.material_type))
                 .order_by(Material.name).all())
    return templates.TemplateResponse("materials/list.html", {
        "request": request,
        "materials": materials,
        "units": MATERIAL_UNITS,
        "error_msg": error
    })


@router.get("/materials/new", response_class=HTMLResponse)
async def new_material_form(request: Request, db: Session = Depends(get_db)):
    """Formular für neues Material"""
    return templates.TemplateResponse("materials/form.html", {
        "request": request,
        "material": None,
        "brands": db.query(Brand).order_by(Brand.name).all(),
        "material_types": get_material_types(db),
        "units": MATERIAL_UNITS,
        "title": "Neues Material"
    })


@router.post("/materials")
async def create_material(
    request: Request,
    name: str = Form(...),
    material_type_id: int = Form(...),
    brand: str = Form(""),
    color: str = Form(""),
    unit: str = Form(...),
    price_per_unit: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neues Material erstellen"""
    values = parse_material_form(db, name, material_type_id, brand, color, unit, price_per_unit, description)
    material = Material()
    apply_material_form(db, material, values)
    db.add(material)
    db.commit()
    return RedirectResponse(url="/materials", status_code=303)


@router.post("/api/materials")
async def create_material_json(
    name: str = Form(...),
    material_type_id: int = Form(...),
    brand: str = Form(""),
    color: str = Form(""),
    unit: str = Form(...),
    price_per_unit: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Neues Material erstellen und als JSON zurückgeben (für den Dialog im Produkt-Formular)"""
    try:
        values = parse_material_form(db, name, material_type_id, brand, color, unit, price_per_unit, description)
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    material = Material()
    apply_material_form(db, material, values)
    db.add(material)
    db.commit()
    db.refresh(material)
    return JSONResponse(material_to_json(material), status_code=201)


@router.get("/materials/{material_id}/edit", response_class=HTMLResponse)
async def edit_material_form(material_id: int, request: Request, db: Session = Depends(get_db)):
    """Material bearbeiten"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")

    return templates.TemplateResponse("materials/form.html", {
        "request": request,
        "material": material,
        "brands": db.query(Brand).order_by(Brand.name).all(),
        "material_types": get_material_types(db),
        "units": MATERIAL_UNITS,
        "title": "Material bearbeiten"
    })


@router.post("/materials/{material_id}/update")
async def update_material(
    material_id: int,
    request: Request,
    name: str = Form(...),
    material_type_id: int = Form(...),
    brand: str = Form(""),
    color: str = Form(""),
    unit: str = Form(...),
    price_per_unit: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Material aktualisieren"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")

    values = parse_material_form(db, name, material_type_id, brand, color, unit, price_per_unit, description)
    apply_material_form(db, material, values)
    material.updated_at = datetime.utcnow()

    db.commit()
    return RedirectResponse(url="/materials", status_code=303)


@router.post("/materials/{material_id}/delete")
async def delete_material(material_id: int, db: Session = Depends(get_db)):
    """Material löschen (nur wenn kein Produkt es verwendet)"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")

    usage = (db.query(ProductMaterial).filter(ProductMaterial.material_id == material_id).count()
             + db.query(ProductPackaging).filter(ProductPackaging.material_id == material_id).count())
    if usage:
        return RedirectResponse(
            url=f"/materials?error=„{material.name}“ wird in {usage} Produkt-Zeile(n) verwendet und kann nicht gelöscht werden.",
            status_code=303)

    db.delete(material)
    db.commit()
    return RedirectResponse(url="/materials", status_code=303)


# =============================================================================
# MATERIAL TYPEN ROUTES
# =============================================================================

@router.get("/material-types", response_class=HTMLResponse)
async def list_material_types(request: Request, db: Session = Depends(get_db)):
    """Liste aller Materialtypen"""
    material_types = db.query(MaterialType).order_by(MaterialType.name).all()
    return templates.TemplateResponse("materials/type_list.html", {
        "request": request,
        "material_types": material_types,
        "title": "Materialtypen"
    })


@router.get("/material-types/new", response_class=HTMLResponse)
async def new_material_type_form(request: Request):
    """Formular für neuen Materialtyp"""
    return templates.TemplateResponse("materials/type_form.html", {
        "request": request,
        "material_type": None,
        "title": "Neuer Materialtyp"
    })


@router.post("/material-types")
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


@router.get("/material-types/{type_id}/edit", response_class=HTMLResponse)
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


@router.post("/material-types/{type_id}/update")
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


@router.post("/material-types/{type_id}/delete")
async def delete_material_type(type_id: int, db: Session = Depends(get_db)):
    """Materialtyp löschen"""
    material_type = db.query(MaterialType).filter(MaterialType.id == type_id).first()
    if not material_type:
        raise HTTPException(status_code=404, detail="Materialtyp nicht gefunden")

    # Prüfe ob Materialien diesen Typ verwenden
    usage_count = db.query(Material).filter(Material.material_type_id == material_type.id).count()
    if usage_count > 0:
        # Soft-delete: auf inaktiv setzen
        material_type.is_active = 0
        db.commit()
    else:
        db.delete(material_type)
        db.commit()

    return RedirectResponse(url="/material-types", status_code=303)
