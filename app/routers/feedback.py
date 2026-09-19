"""Feedback und Ideen."""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from core import templates
from database import get_db
from models import (
    FeedbackIdea,
)

router = APIRouter()


@router.get("/feedback-ideas", response_class=HTMLResponse)
async def list_feedback_ideas(request: Request, db: Session = Depends(get_db)):
    """Liste aller Feedback-Einträge und Ideen (neueste zuerst); Filtern passiert im Browser (Spaltenköpfe)."""
    items = db.query(FeedbackIdea).order_by(FeedbackIdea.created_at.desc()).all()
    return templates.TemplateResponse("feedback_ideas/list.html", {
        "request": request,
        "items": items
    })


@router.get("/feedback-ideas/new", response_class=HTMLResponse)
async def new_feedback_idea_form(request: Request):
    """Formular für neues Feedback / neue Idee"""
    return templates.TemplateResponse("feedback_ideas/form.html", {
        "request": request,
        "item": None,
        "title": "Neues Feedback / Idee"
    })


@router.post("/feedback-ideas")
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


@router.get("/feedback-ideas/{item_id}/edit", response_class=HTMLResponse)
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


@router.post("/feedback-ideas/{item_id}/update")
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


@router.post("/feedback-ideas/{item_id}/status")
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


@router.post("/feedback-ideas/{item_id}/delete")
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
