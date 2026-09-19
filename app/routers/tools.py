"""Werkzeuge: PNG zu SVG Konverter und Bibliothek."""
from datetime import datetime
from pathlib import Path
import os
import shutil
import uuid

import vtracer
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from core import templates
from database import get_db
from models import (
    ConvertedFile,
)

router = APIRouter()


# Verzeichnis fuer temporaere Uploads
UPLOAD_DIR = Path("/tmp/picocalc_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Permanentes Speicherverzeichnis (Docker Volume)
FILE_STORAGE_PATH = Path(os.environ.get("FILE_STORAGE_PATH", "/app/storage"))
FILE_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

@router.get("/tools/png-to-svg", response_class=HTMLResponse)
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

@router.post("/tools/png-to-svg")
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

@router.post("/tools/png-to-svg/download")
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

@router.get("/tools/converted-files", response_class=HTMLResponse)
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

@router.get("/tools/converted-files/{file_id}/preview", response_class=HTMLResponse)
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

@router.get("/tools/converted-files/{file_id}/download/svg")
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

@router.get("/tools/converted-files/{file_id}/download/png")
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

@router.post("/tools/converted-files/{file_id}/delete")
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
