"""Produkte: Liste, Kalkulator-Formular, Detail, Löschen und JSON-Schnittstellen."""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from core import templates
from database import get_db
from models import (
    EventItem, Product, load_calc_settings,
)
from product_service import (
    PRODUCT_LOAD_OPTIONS, CalculationIn, apply_product_form, parse_product_form, preview_costs, product_form_context,
)
from units import MATERIAL_UNITS

router = APIRouter()


@router.get("/products", response_class=HTMLResponse)
async def list_products(
    request: Request,
    market_filter: str = "",
    search: str = "",
    sort_by: str = "name",
    sort_order: str = "asc",
    db: Session = Depends(get_db)
):
    """Liste aller Produkte"""
    query = db.query(Product).options(*PRODUCT_LOAD_OPTIONS)

    if market_filter == "market":
        query = query.filter(Product.is_for_market.is_(True))
    elif market_filter == "non_market":
        query = query.filter(Product.is_for_market.is_(False))
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    if sort_by == "updated_at":
        query = query.order_by(Product.updated_at.asc() if sort_order == "asc" else Product.updated_at.desc())
    else:
        query = query.order_by(Product.name.desc() if sort_order == "desc" and sort_by == "name" else Product.name.asc())

    settings = load_calc_settings(db)
    products_with_costs = [{'product': p, 'costs': p.calculate_costs(settings)} for p in query.all()]

    # Python-seitige Sortierung für abgeleitete/berechnete Felder
    descending = sort_order == "desc"
    if sort_by == "type":
        products_with_costs.sort(key=lambda x: x['product'].type_label.lower(), reverse=descending)
    elif sort_by == "purchase_price":
        products_with_costs.sort(key=lambda x: x['costs']['purchase_price'], reverse=descending)
    elif sort_by == "selling_price":
        products_with_costs.sort(key=lambda x: x['costs']['selling_price'], reverse=descending)

    return templates.TemplateResponse("products/list.html", {
        "request": request,
        "products": products_with_costs,
        "market_filter": market_filter,
        "search": search,
        "sort_by": sort_by,
        "sort_order": sort_order
    })


@router.post("/products/{product_id}/toggle-market")
async def toggle_product_market_status(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Flohmarkt-Status eines Produkts umschalten"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")

    product.is_for_market = not product.is_for_market
    product.updated_at = datetime.utcnow()
    db.commit()

    if request.headers.get("hx-request"):
        return Response(status_code=204)
    return RedirectResponse(url=request.headers.get("referer", "/products"), status_code=303)


@router.post("/products/bulk-toggle-market")
async def bulk_toggle_product_market_status(
    request: Request,
    product_ids: str = Form(...),
    is_for_market: int = Form(...),
    db: Session = Depends(get_db)
):
    """Mehrere Produkte gleichzeitig auf Flohmarkt-Verfügbarkeit setzen"""
    try:
        ids = [int(x.strip()) for x in product_ids.split(",") if x.strip()]
        if ids:
            db.query(Product).filter(Product.id.in_(ids)).update(
                {Product.is_for_market: bool(is_for_market), Product.updated_at: datetime.utcnow()},
                synchronize_session=False
            )
            db.commit()
    except Exception as e:
        print(f"Error in bulk_toggle_product_market_status: {e}")

    if request.headers.get("hx-request"):
        return Response(status_code=204)
    return RedirectResponse(url=request.headers.get("referer", "/products"), status_code=303)


@router.get("/products/new", response_class=HTMLResponse)
async def new_product_form(request: Request, db: Session = Depends(get_db)):
    """Produkt-Kalkulator (Rezept- und Ausbeute-Prinzip)"""
    return templates.TemplateResponse("products/form_universal.html", product_form_context(db, request))


@router.post("/products")
async def create_product(
    request: Request,
    name: str = Form(...),
    category_id: int = Form(None),
    notes: str = Form(""),
    batch_yield: str = Form("1"),
    shipping_cost: str = Form("0"),
    selling_price: str = Form(None),
    is_for_market: str = Form(None),
    used_material_id: list[str] = Form([]),
    used_material_amount: list[str] = Form([]),
    used_machine_id: list[str] = Form([]),
    used_machine_value: list[str] = Form([]),
    used_labor_description: list[str] = Form([]),
    used_labor_minutes: list[str] = Form([]),
    used_labor_rate: list[str] = Form([]),
    used_packaging_id: list[str] = Form([]),
    used_packaging_amount: list[str] = Form([]),
    db: Session = Depends(get_db)
):
    """Neues Produkt aus dem Kalkulator erstellen"""
    data = parse_product_form(
        db, name=name, category_id=category_id, notes=notes, batch_yield=batch_yield,
        shipping_cost=shipping_cost, selling_price=selling_price, is_for_market=is_for_market,
        used_material_id=used_material_id, used_material_amount=used_material_amount,
        used_machine_id=used_machine_id, used_machine_value=used_machine_value,
        used_labor_description=used_labor_description, used_labor_minutes=used_labor_minutes,
        used_labor_rate=used_labor_rate, used_packaging_id=used_packaging_id,
        used_packaging_amount=used_packaging_amount,
    )
    product = Product()
    apply_product_form(product, data)
    db.add(product)
    db.commit()
    db.refresh(product)

    return RedirectResponse(url=f"/products/{product.id}?success=Produkt+erfolgreich+erstellt", status_code=303)


@router.get("/products/{product_id}", response_class=HTMLResponse)
async def view_product(
    product_id: int,
    request: Request,
    success: str = "",
    error: str = "",
    db: Session = Depends(get_db)
):
    """Produktdetails anzeigen"""
    product = db.query(Product).options(*PRODUCT_LOAD_OPTIONS).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")

    return templates.TemplateResponse("products/detail.html", {
        "request": request,
        "product": product,
        "calc": product.calculate_costs(),
        "units": MATERIAL_UNITS,
        "success_msg": success,
        "error_msg": error
    })


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def edit_product_form(product_id: int, request: Request, db: Session = Depends(get_db)):
    """Produkt bearbeiten - Kalkulator-Formular"""
    product = db.query(Product).options(*PRODUCT_LOAD_OPTIONS).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")

    return templates.TemplateResponse("products/form_universal.html", product_form_context(db, request, product))


@router.post("/products/{product_id}/update")
async def update_product(
    product_id: int,
    request: Request,
    name: str = Form(...),
    category_id: int = Form(None),
    notes: str = Form(""),
    batch_yield: str = Form("1"),
    shipping_cost: str = Form("0"),
    selling_price: str = Form(None),
    is_for_market: str = Form(None),
    used_material_id: list[str] = Form([]),
    used_material_amount: list[str] = Form([]),
    used_machine_id: list[str] = Form([]),
    used_machine_value: list[str] = Form([]),
    used_labor_description: list[str] = Form([]),
    used_labor_minutes: list[str] = Form([]),
    used_labor_rate: list[str] = Form([]),
    used_packaging_id: list[str] = Form([]),
    used_packaging_amount: list[str] = Form([]),
    db: Session = Depends(get_db)
):
    """Produkt aktualisieren"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")

    data = parse_product_form(
        db, name=name, category_id=category_id, notes=notes, batch_yield=batch_yield,
        shipping_cost=shipping_cost, selling_price=selling_price, is_for_market=is_for_market,
        used_material_id=used_material_id, used_material_amount=used_material_amount,
        used_machine_id=used_machine_id, used_machine_value=used_machine_value,
        used_labor_description=used_labor_description, used_labor_minutes=used_labor_minutes,
        used_labor_rate=used_labor_rate, used_packaging_id=used_packaging_id,
        used_packaging_amount=used_packaging_amount,
    )
    apply_product_form(product, data)
    product.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url=f"/products/{product_id}?success=Produkt+erfolgreich+aktualisiert", status_code=303)


@router.post("/products/{product_id}/delete")
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Produkt löschen (Materialien/Maschinen der Charge werden mitgelöscht)"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")

    # Event-Items behalten ihren Eintrag, verlieren aber die Produkt-Verknüpfung
    db.query(EventItem).filter(EventItem.product_id == product_id).update(
        {EventItem.product_id: None}
    )

    db.delete(product)
    db.commit()

    return RedirectResponse(url="/products?success=Produkt+wurde+gelöscht", status_code=303)


@router.post("/api/calculate")
async def api_calculate(data: CalculationIn, db: Session = Depends(get_db)):
    """Live-Kalkulation für den Produkt-Kalkulator. Rechnet ungespeicherte Eingaben mit derselben
    Funktion wie das gespeicherte Produkt, damit Vorschau und Detailseite nie abweichen."""
    return preview_costs(db, data)


@router.get("/api/products/search")
async def api_search_products(q: str = "", db: Session = Depends(get_db)):
    """API: Produkte suchen (für Autocomplete)"""
    query = db.query(Product).options(*PRODUCT_LOAD_OPTIONS)
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    settings = load_calc_settings(db)
    return [
        {
            "id": p.id,
            "name": p.name,
            "product_type": p.type_label,
            "cost": p.calculate_costs(settings)["total_cost"]
        }
        for p in query.order_by(Product.name).limit(20).all()
    ]


@router.get("/api/products/{product_id}/details")
async def api_product_details(product_id: int, db: Session = Depends(get_db)):
    """API: Produktdetails"""
    product = db.query(Product).options(*PRODUCT_LOAD_OPTIONS).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")

    return {
        "id": product.id,
        "name": product.name,
        "product_type": product.type_label,
        "total_cost": product.calculate_costs()["total_cost"]
    }
