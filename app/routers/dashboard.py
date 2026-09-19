"""Dashboard (Startseite)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from core import templates
from database import get_db
from models import Machine, MarketEvent, Material, Product, load_calc_settings
from product_service import PRODUCT_LOAD_OPTIONS

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
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

    settings = load_calc_settings(db)
    all_products = db.query(Product).options(*PRODUCT_LOAD_OPTIONS).all()
    avg_cost = 0
    if all_products:
        total = sum(p.calculate_costs(settings)['total_cost'] for p in all_products)
        avg_cost = total / len(all_products)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "products": products,
        "total_products": total_products,
        "total_materials": total_materials,
        "total_machines": total_machines,
        "avg_cost": round(avg_cost, 2),
        "upcoming_events": upcoming_events,
        "calc_settings": settings
    })
