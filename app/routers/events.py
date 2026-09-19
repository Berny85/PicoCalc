"""Flohmärkte/Events: Vorproduktion, Materialbedarf und Packliste."""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from common import (
    parse_decimal,
)
from core import templates
from database import get_db
from models import (
    EventItem, EventTodo, MarketEvent, Product,
)

router = APIRouter()


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


@router.get("/events", response_class=HTMLResponse)
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
            (MarketEvent.description.ilike(search_pattern)) |
            (MarketEvent.product_ideas.ilike(search_pattern))
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


@router.get("/events/new", response_class=HTMLResponse)
async def new_event_form(request: Request):
    """Neues Event anlegen Formular"""
    return templates.TemplateResponse("events/form.html", {
        "request": request,
        "event": None,
        "is_edit": False
    })


@router.post("/events/new")
async def create_event(
    request: Request,
    name: str = Form(...),
    event_date: str = Form(None),
    location: str = Form(None),
    description: str = Form(None),
    product_ideas: str = Form(None),
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
        product_ideas=product_ideas.strip() if product_ideas else None,
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


@router.get("/events/{event_id}", response_class=HTMLResponse)
async def event_detail(event_id: int, request: Request, db: Session = Depends(get_db)):
    """Detailansicht & Dashboard für ein einzelnes Event"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    totals = event.calculate_totals()
    market_products = db.query(Product).filter(Product.is_for_market.is_(True)).order_by(Product.name.asc()).all()
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


@router.get("/events/{event_id}/edit", response_class=HTMLResponse)
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


@router.post("/events/{event_id}/update")
async def update_event(
    event_id: int,
    request: Request,
    name: str = Form(...),
    event_date: str = Form(None),
    location: str = Form(None),
    description: str = Form(None),
    product_ideas: str = Form(None),
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
    event.product_ideas = product_ideas.strip() if product_ideas else None
    event.status = status
    event.updated_at = datetime.utcnow()
    
    db.commit()
    return RedirectResponse(url=f"/events/{event.id}", status_code=303)


@router.post("/events/{event_id}/ideas")
async def update_event_ideas(
    event_id: int,
    request: Request,
    product_ideas: str = Form(None),
    db: Session = Depends(get_db)
):
    """Produkt-Ideen & Chat-Brainstorming schnell speichern"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    event.product_ideas = product_ideas.strip() if product_ideas else None
    event.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"/events/{event.id}#product-ideas", status_code=303)


@router.post("/events/{event_id}/status")
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


@router.post("/events/{event_id}/delete")
async def delete_event(event_id: int, db: Session = Depends(get_db)):
    """Event löschen"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    db.delete(event)
    db.commit()
    return RedirectResponse(url="/events", status_code=303)


@router.post("/events/{event_id}/items/add")
async def add_event_item(
    event_id: int,
    product_id: int = Form(None),
    target_quantity: int = Form(1),
    custom_vk: str = Form(None),
    notes: str = Form(None),
    db: Session = Depends(get_db)
):
    """Produkt zur Vorproduktionsliste hinzufügen mit optionalem individuellem Flohmarkt-VK"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    parsed_custom_vk = None
    if custom_vk and custom_vk.strip():
        val = parse_decimal(custom_vk)
        if val > 0:
            parsed_custom_vk = val
            
    # Prüfen ob Artikel bereits vorhanden -> dann Soll-Menge erhöhen
    existing_item = db.query(EventItem).filter(
        EventItem.event_id == event_id,
        EventItem.product_id == product_id
    ).first() if product_id else None
    
    if existing_item:
        existing_item.target_quantity += max(1, target_quantity)
        if parsed_custom_vk is not None:
            existing_item.custom_vk = parsed_custom_vk
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
            custom_vk=parsed_custom_vk,
            notes=notes.strip() if notes else None
        )
        db.add(new_item)
        
    db.commit()
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@router.post("/events/{event_id}/items/{item_id}/update-vk")
async def update_event_item_vk(
    event_id: int,
    item_id: int,
    custom_vk: str = Form(None),
    db: Session = Depends(get_db)
):
    """Individuellen Flohmarkt-VK eines Artikels aktualisieren"""
    item = db.query(EventItem).filter(EventItem.id == item_id, EventItem.event_id == event_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
        
    if custom_vk and custom_vk.strip():
        val = parse_decimal(custom_vk)
        item.custom_vk = val if val > 0 else None
    else:
        item.custom_vk = None
        
    item.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@router.post("/events/{event_id}/items/{item_id}/adjust")
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


@router.post("/events/{event_id}/items/{item_id}/delete")
async def delete_event_item(event_id: int, item_id: int, db: Session = Depends(get_db)):
    """Artikel aus Vorproduktion löschen"""
    item = db.query(EventItem).filter(EventItem.id == item_id, EventItem.event_id == event_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
        
    db.delete(item)
    db.commit()
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@router.post("/events/{event_id}/todos/add")
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


@router.post("/events/{event_id}/todos/{todo_id}/toggle")
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


@router.post("/events/{event_id}/todos/{todo_id}/delete")
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


@router.post("/events/{event_id}/todos/load-template")
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


@router.post("/events/{event_id}/todos/bulk-toggle")
async def bulk_toggle_event_todos(
    event_id: int,
    request: Request,
    is_done: int = Form(...),
    category: str = Form(None),
    db: Session = Depends(get_db)
):
    """Mehrere ToDos auf einmal als erledigt oder unerledigt markieren"""
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
        
    query = db.query(EventTodo).filter(EventTodo.event_id == event_id)
    if category and category.strip():
        query = query.filter(EventTodo.category == category.strip())
        
    query.update({EventTodo.is_done: is_done, EventTodo.updated_at: datetime.utcnow()}, synchronize_session=False)
    db.commit()
    
    return RedirectResponse(url=f"/events/{event_id}#todos", status_code=303)


@router.get("/events/{event_id}/print", response_class=HTMLResponse)
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
