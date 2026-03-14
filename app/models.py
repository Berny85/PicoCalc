from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

# Konstanten
STROM_PREIS_KWH = 0.22  # €/kWh

class Machine(Base):
    """Maschinen-Tabelle (Drucker, Plotter, etc.)"""
    __tablename__ = "machines"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    machine_type = Column(String(50), nullable=False)  # 3d_printer, cutter_plotter, etc.
    description = Column(Text, nullable=True)
    
    # Kostenparameter (zeitbasiert - für 3D-Drucker, etc.)
    depreciation_euro = Column(Numeric(10, 2), nullable=False, default=0)  # Abschreibung pro Gerät
    lifespan_hours = Column(Numeric(10, 2), nullable=False, default=1)  # Lebensdauer in Stunden
    power_kw = Column(Numeric(5, 3), nullable=False, default=0)  # Stromverbrauch in kW
    
    # Kostenparameter (seitenbasiert - für Tintenstrahl-Drucker)
    lifespan_pages = Column(Numeric(10, 0), nullable=True)  # Lebensdauer in Seiten
    depreciation_per_page = Column(Numeric(10, 4), nullable=True)  # Abschreibung pro Seite (€)
    
    # Kostenparameter (bogenbasiert - für Plotter/Drucker bei Sticker-Produktion)
    cost_per_sheet = Column(Numeric(10, 4), nullable=True)  # Kosten pro Bogen (€)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"{self.name} ({self.machine_type})"
    
    def calculate_cost_per_hour(self):
        """Berechnet Maschinenkosten pro Stunde (für zeitbasierte Maschinen)"""
        if self.machine_type == 'inkjet_printer':
            return 0.0  # Tintenstrahl-Drucker rechnen pro Seite, nicht pro Stunde
        strom_kosten = STROM_PREIS_KWH * float(self.power_kw)
        abschreibung = float(self.depreciation_euro) / float(self.lifespan_hours)
        return strom_kosten + abschreibung
    
    def calculate_cost_per_page(self):
        """Berechnet Maschinenkosten pro Seite (für Tintenstrahl-Drucker)"""
        if self.machine_type == 'inkjet_printer' and self.depreciation_per_page:
            return float(self.depreciation_per_page)
        return 0.0
    
    def calculate_cost_per_sheet(self):
        """Berechnet Maschinenkosten pro Bogen (für Plotter/Drucker bei Sticker-Produktion)"""
        if self.cost_per_sheet:
            return float(self.cost_per_sheet)
        return 0.0
    
    def calculate_cost_per_unit(self, production_hours=0, pages=0, sheets=0):
        """Berechnet Gesamtkosten für Produktion (zeitbasiert, seitenbasiert oder bogenbasiert)"""
        if self.machine_type == 'inkjet_printer':
            return pages * self.calculate_cost_per_page()
        elif sheets > 0 and self.cost_per_sheet:
            # Bogenbasierte Berechnung (für Plotter/Drucker)
            return sheets * self.calculate_cost_per_sheet()
        # Zeitbasierte Berechnung (Standard)
        return production_hours * self.calculate_cost_per_hour()


class MaterialType(Base):
    """Materialtypen - konfigurierbare Liste (Filament, Sticker-Sheet, etc.)
"""
    __tablename__ = "material_types"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), nullable=False, unique=True)  # Interner Schlüssel (z.B. 'filament')
    name = Column(String(100), nullable=False)  # Anzeigename (z.B. '3D-Filament (€/kg)')
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)  # Für Reihenfolge in Dropdowns
    is_active = Column(Integer, default=1)  # 1 = aktiv, 0 = inaktiv
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"{self.name} ({self.key})"


class Material(Base):
    """Material-Tabelle für Filamente, Papier, Sticker-Sheets, etc.
"""
    __tablename__ = "materials"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    material_type = Column(String(50), nullable=False)  # Verweist auf material_types.key
    brand = Column(String(100), nullable=True)
    color = Column(String(50), nullable=True)
    unit = Column(String(20), nullable=False)  # kg, sheet, m, piece, etc.
    price_per_unit = Column(Numeric(10, 2), nullable=False)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"{self.name} ({self.material_type})"


class Product(Base):
    """Produkte - mit typ-spezifischen Feldern"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    product_type = Column(String(50), nullable=False)  # '3d_print', 'sticker_sheet', 'diecut_sticker', etc.
    category = Column(String(100), default="Sonstiges")
    
    # === 3D-DRUCK SPEZIFISCH ===
    filament_material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    filament_weight_g = Column(Numeric(10, 2), nullable=True)  # Gewicht in Gramm
    print_time_hours = Column(Numeric(5, 2), nullable=True)  # Druckzeit
    
    # === STICKER/PAPIER SPEZIFISCH ===
    sheet_material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    sheet_count = Column(Numeric(10, 2), nullable=True)  # Anzahl Bögen
    cut_time_hours = Column(Numeric(5, 2), nullable=True)  # Schneidezeit
    units_per_sheet = Column(Numeric(10, 2), default=1)  # Wie viele Produkte pro Bogen (z.B. 3 Bögen pro Material, oder 9 Sticker pro Bogen)
    
    # === LASER-GRAVUR SPEZIFISCH ===
    laser_material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    laser_design_name = Column(String(255), nullable=True)  # z.B. "Logo Pico"
    
    # === LASER LAYER 1 ===
    laser1_type = Column(String(50), nullable=True)  # "blau" oder "ir" oder "rot"
    laser1_power_percent = Column(Numeric(5, 2), nullable=True)  # Power in %
    laser1_speed_mm_s = Column(Numeric(10, 2), nullable=True)  # Geschwindigkeit in mm/s
    laser1_passes = Column(Integer, default=1)  # Anzahl Durchläufe
    laser1_dpi = Column(Integer, nullable=True)  # DPI
    laser1_lines_per_cm = Column(Integer, nullable=True)  # Lines per cm
    
    # === LASER LAYER 2 ===
    laser2_type = Column(String(50), nullable=True)
    laser2_power_percent = Column(Numeric(5, 2), nullable=True)
    laser2_speed_mm_s = Column(Numeric(10, 2), nullable=True)
    laser2_passes = Column(Integer, nullable=True)
    laser2_dpi = Column(Integer, nullable=True)
    laser2_lines_per_cm = Column(Integer, nullable=True)
    
    # === LASER LAYER 3 ===
    laser3_type = Column(String(50), nullable=True)
    laser3_power_percent = Column(Numeric(5, 2), nullable=True)
    laser3_speed_mm_s = Column(Numeric(10, 2), nullable=True)
    laser3_passes = Column(Integer, nullable=True)
    laser3_dpi = Column(Integer, nullable=True)
    laser3_lines_per_cm = Column(Integer, nullable=True)
    
    # === WICHTIG: Maschinen-Auswahl ===
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    additional_machine_ids = Column(String(255), nullable=True)  # Kommaseparierte IDs für zusätzliche Maschinen (z.B. "2,3")
    
    # === ARBEIT ===
    labor_minutes = Column(Numeric(10, 2), default=0)
    labor_rate_per_hour = Column(Numeric(10, 2), default=20.00)
    
    # === KOSTEN ===
    packaging_cost = Column(Numeric(10, 2), default=0)
    shipping_cost = Column(Numeric(10, 2), default=0)
    
    # === BERECHNUNGSMODUS ===
    # "per_unit" = Kosten pro Einheit (altes Verhalten, Standard)
    # "per_batch" = Kosten gelten für Batch, werden auf Einheit umgerechnet
    calculation_mode = Column(String(20), default="per_unit")
    units_per_batch = Column(Integer, default=1)  # Anzahl Einheiten pro Produktionsvorgang
    
    # === NOTIZEN ===
    notes = Column(Text, nullable=True)
    
    # === TIMESTAMPS ===
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # === BEZIEHUNGEN ===
    filament_material = relationship("Material", foreign_keys=[filament_material_id])
    sheet_material = relationship("Material", foreign_keys=[sheet_material_id])
    laser_material = relationship("Material", foreign_keys=[laser_material_id])
    machine = relationship("Machine", backref="products")
    
    def get_machine_cost_per_hour(self):
        """Maschinenkosten pro Stunde"""
        if self.machine:
            return self.machine.calculate_cost_per_hour()
        return 0.0
    
    def calculate_3d_print_costs(self):
        """Kalkulation für 3D-Druck"""
        costs = {'type': '3d_print'}
        
        # Filamentkosten
        if self.filament_material_id and self.filament_material:
            filament_price_per_kg = float(self.filament_material.price_per_unit)
            filament_cost = (float(self.filament_weight_g) / 1000) * filament_price_per_kg
            costs['filament_info'] = f"{self.filament_material.name}"
        else:
            filament_cost = 0
            costs['filament_info'] = "Kein Filament"
        
        costs['filament_cost'] = round(filament_cost, 2)
        
        # Druckkosten (Druckzeit)
        machine_cost_per_h = self.get_machine_cost_per_hour()
        print_cost = float(self.print_time_hours or 0) * machine_cost_per_h
        costs['machine_cost'] = round(print_cost, 2)
        costs['machine_cost_per_hour'] = round(machine_cost_per_h, 3)
        costs['print_time_hours'] = float(self.print_time_hours or 0)
        
        return costs
    
    def calculate_sticker_costs(self):
        """Kalkulation für Sticker/Papier/DieCut"""
        costs = {'type': self.product_type}
        
        # Materialkosten (Bögen)
        if self.sheet_material_id and self.sheet_material:
            sheet_price = float(self.sheet_material.price_per_unit)
            total_material_cost = float(self.sheet_count or 0) * sheet_price
            costs['sheet_info'] = f"{self.sheet_material.name}"
        else:
            total_material_cost = 0
            costs['sheet_info'] = "Kein Material"
        
        # Maschinenkosten (Plotter/Drucker - pro Bogen)
        total_machine_cost = 0.0
        if self.machine_id and self.machine:
            # Maschine mit cost_per_sheet (Plotter/Drucker)
            total_machine_cost = self.machine.calculate_cost_per_unit(sheets=float(self.sheet_count or 0))
            costs['machine_info'] = f"{self.machine.name}"
            costs['cost_per_sheet'] = self.machine.calculate_cost_per_sheet()
        else:
            costs['machine_info'] = "Keine Maschine"
            costs['cost_per_sheet'] = 0.0
        
        costs['total_machine_cost'] = round(total_machine_cost, 2)
        costs['sheet_count'] = float(self.sheet_count or 0)
        
        # Berechnung basierend auf calculation_mode
        if self.calculation_mode == 'per_batch':
            # Kosten gelten für den gesamten Batch
            batch_material_cost = total_material_cost
            batch_machine_cost = total_machine_cost
            batch_size = self.units_per_batch if self.units_per_batch > 0 else 1
            
            # Kosten pro Einheit = Batch-Kosten / Batch-Größe
            material_cost_per_unit = batch_material_cost / batch_size
            machine_cost_per_unit = batch_machine_cost / batch_size
            
            costs['calculation_mode'] = 'per_batch'
            costs['units_per_batch'] = batch_size
            costs['batch_material_cost'] = round(batch_material_cost, 2)
            costs['batch_machine_cost'] = round(batch_machine_cost, 2)
        else:
            # Standard: pro Einheit (altes Verhalten)
            units_per_sheet = float(self.units_per_sheet or 1)
            if units_per_sheet > 0:
                material_cost_per_unit = total_material_cost / units_per_sheet
            else:
                material_cost_per_unit = total_material_cost
            
            # Maschinenkosten auch auf Einheit umrechnen
            if units_per_sheet > 0:
                machine_cost_per_unit = total_machine_cost / units_per_sheet
            else:
                machine_cost_per_unit = total_machine_cost
            
            costs['calculation_mode'] = 'per_unit'
            costs['units_per_sheet'] = units_per_sheet
        
        costs['material_cost'] = round(material_cost_per_unit, 2)
        costs['machine_cost'] = round(machine_cost_per_unit, 2)
        costs['total_material_cost'] = round(total_material_cost, 2)
        costs['cut_time_hours'] = 0
        
        return costs
    
    def calculate_laser_costs(self):
        """Kalkulation für Laser-Gravuren"""
        costs = {'type': 'laser_engraving'}
        
        # Materialkosten
        if self.laser_material_id and self.laser_material:
            material_price = float(self.laser_material.price_per_unit)
            costs['material_info'] = f"{self.laser_material.name}"
            costs['material_cost'] = round(material_price, 2)
        else:
            costs['material_info'] = "Kein Material"
            costs['material_cost'] = 0
        
        # Layer 1 (immer vorhanden)
        costs['layer1'] = {
            'type': self.laser1_type or "-",
            'power': float(self.laser1_power_percent or 0),
            'speed': float(self.laser1_speed_mm_s or 0),
            'passes': int(self.laser1_passes or 1),
            'dpi': int(self.laser1_dpi or 0),
            'lines_per_cm': int(self.laser1_lines_per_cm or 0)
        }
        
        # Layer 2 (optional)
        costs['layer2'] = None
        if self.laser2_type:
            costs['layer2'] = {
                'type': self.laser2_type,
                'power': float(self.laser2_power_percent or 0),
                'speed': float(self.laser2_speed_mm_s or 0),
                'passes': int(self.laser2_passes or 1),
                'dpi': int(self.laser2_dpi or 0),
                'lines_per_cm': int(self.laser2_lines_per_cm or 0)
            }
        
        # Layer 3 (optional)
        costs['layer3'] = None
        if self.laser3_type:
            costs['layer3'] = {
                'type': self.laser3_type,
                'power': float(self.laser3_power_percent or 0),
                'speed': float(self.laser3_speed_mm_s or 0),
                'passes': int(self.laser3_passes or 1),
                'dpi': int(self.laser3_dpi or 0),
                'lines_per_cm': int(self.laser3_lines_per_cm or 0)
            }
        
        costs['machine_cost'] = 0  # Keine Maschinenkosten berechnet
        
        return costs
    
    def calculate_assembly_costs(self):
        """Kalkulation für Zusammenbau-Produkte (Assembly)"""
        costs = {'type': 'assembly'}
        
        # Summiere alle Komponenten-Kosten
        total_components_cost = 0.0
        components_details = []
        
        for component in self.components:
            component_cost = component.calculate_total_cost()
            total_components_cost += component_cost
            components_details.append({
                'name': component.name,
                'quantity': float(component.quantity),
                'unit_cost': float(component.unit_cost),
                'total': round(component_cost, 2),
                'notes': component.notes
            })
        
        costs['material_cost'] = round(total_components_cost, 2)
        costs['components'] = components_details
        costs['components_count'] = len(components_details)
        costs['machine_cost'] = 0  # Keine Maschinenkosten beim Zusammenbau
        
        return costs
    
    def calculate_costs(self):
        """Hauptkalkulation je nach Produkttyp"""
        # Typ-spezifische Kosten
        if self.product_type == '3d_print':
            type_costs = self.calculate_3d_print_costs()
            material_cost = type_costs['filament_cost']
            machine_cost = type_costs['machine_cost']
        elif self.product_type in ['sticker_sheet', 'diecut_sticker', 'stationery', 'paper']:
            type_costs = self.calculate_sticker_costs()
            material_cost = type_costs['material_cost']
            machine_cost = type_costs['machine_cost']
        elif self.product_type == 'laser_engraving':
            type_costs = self.calculate_laser_costs()
            material_cost = type_costs['material_cost']
            machine_cost = type_costs['machine_cost']
        elif self.product_type == 'assembly':
            type_costs = self.calculate_assembly_costs()
            material_cost = type_costs['material_cost']
            machine_cost = type_costs['machine_cost']
        else:
            # Generische Berechnung
            type_costs = {'type': 'generic', 'material_cost': 0, 'machine_cost': 0}
            material_cost = 0
            machine_cost = float(self.print_time_hours or 0) * self.get_machine_cost_per_hour()
        
        # Arbeitskosten (labor_minutes ist in Minuten, daher / 60 für Stunden)
        labor_hours = float(self.labor_minutes) / 60.0
        labor_cost = labor_hours * float(self.labor_rate_per_hour)
        
        # Bei per_batch: Arbeitskosten auf Einheit umrechnen
        if self.calculation_mode == 'per_batch' and self.units_per_batch > 0:
            labor_cost_per_unit = labor_cost / self.units_per_batch
            # Arbeitskosten pro Batch (für Anzeige)
            labor_cost_batch = labor_cost
            labor_cost = labor_cost_per_unit
        else:
            labor_cost_batch = labor_cost
        
        # Basis-Kosten (Material + Maschine + Arbeit) pro Einheit
        base_cost_per_unit = material_cost + machine_cost + labor_cost
        
        # Verpackung/Versand (werden separat behandelt)
        packaging_shipping = float(self.packaging_cost) + float(self.shipping_cost)
        
        # Gesamtkosten pro Einheit
        total_cost = base_cost_per_unit
        
        result = {
            'material_cost': round(material_cost, 2),
            'machine_cost': round(machine_cost, 2),
            'machine_cost_per_hour': round(self.get_machine_cost_per_hour(), 3),
            'labor_cost': round(labor_cost, 2),
            'labor_hours': labor_hours,
            'labor_minutes': float(self.labor_minutes),
            'labor_cost_batch': round(labor_cost_batch, 2) if self.calculation_mode == 'per_batch' else None,
            'packaging_shipping': round(packaging_shipping, 2),
            'packaging_cost': float(self.packaging_cost),
            'shipping_cost': float(self.shipping_cost),
            'total_cost': round(total_cost, 2),
            'calculation_mode': self.calculation_mode,
            'units_per_batch': self.units_per_batch if self.calculation_mode == 'per_batch' else None,
            'selling_price_30': round(total_cost * 1.30, 2),
            'selling_price_50': round(total_cost * 1.50, 2),
            'selling_price_100': round(total_cost * 2.00, 2),
        }
        
        # Typ-spezifische Details hinzufügen
        result.update(type_costs)
        
        return result
    
    def get_material_summary(self):
        """Zusammenfassung des verwendeten Materials"""
        if self.product_type == '3d_print' and self.filament_material:
            return f"{self.filament_weight_g}g {self.filament_material.name}"
        elif self.product_type in ['sticker_sheet', 'diecut_sticker', 'paper'] and self.sheet_material:
            return f"{self.sheet_count} {self.sheet_material.unit} {self.sheet_material.name}"
        elif self.product_type == 'laser_engraving':
            if self.laser_material:
                return f"{self.laser_material.name}"
            return "Kein Material angegeben"
        elif self.product_type == 'assembly':
            count = len(self.components)
            if count == 0:
                return "Keine Komponenten"
            elif count == 1:
                return "1 Komponente"
            else:
                return f"{count} Komponenten"
        return "Kein Material"


class Feedback(Base):
    """Feedback-Tabelle für Änderungswünsche und Anregungen"""
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    page_url = Column(String(500), nullable=False)  # Auf welcher Seite wurde Feedback gegeben
    page_title = Column(String(255), nullable=True)  # Titel der Seite
    category = Column(String(50), nullable=False)  # 'bug', 'feature', 'improvement', 'other'
    message = Column(Text, nullable=False)
    user_info = Column(String(100), nullable=True)  # Optional: Wer hat das Feedback gegeben
    status = Column(String(20), default="new")  # 'new', 'in_progress', 'done', 'rejected'
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"Feedback({self.category}: {self.message[:30]}...)"


class Idea(Base):
    """Ideen-Board für schnelles Notieren von Ideen im Kanban-Stil"""
    __tablename__ = "ideas"
    
    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(255), nullable=False)  # Idee (Pflichtfeld)
    content = Column(Text, nullable=True)  # Notizen (optional)
    status = Column(String(20), default="todo")  # 'todo', 'in_progress', 'done'
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"Idea({self.subject or self.content[:30]}...)"


class ConvertedFile(Base):
    """Gespeicherte PNG-zu-SVG Konvertierungen"""
    __tablename__ = "converted_files"
    
    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)  # UUID
    file_path_png = Column(String(500), nullable=False)  # Relativer Pfad zur PNG
    file_path_svg = Column(String(500), nullable=False)  # Relativer Pfad zur SVG
    original_size_bytes = Column(Integer, nullable=True)
    svg_size_bytes = Column(Integer, nullable=True)
    
    # Konvertierungs-Optionen (für Dokumentation/Re-Konvertierung)
    conversion_mode = Column(String(50), default="spline")  # 'spline' oder 'pixel'
    color_mode = Column(String(50), default="color")  # 'color' oder 'binary'
    
    # Optional: Beschreibung/Tags für die Suche
    description = Column(String(500), nullable=True)
    tags = Column(String(255), nullable=True)  # Komma-getrennte Tags
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"ConvertedFile({self.original_filename})"
    
    def get_size_reduction_percent(self):
        """Berechnet die Größenreduktion in Prozent"""
        if self.original_size_bytes and self.svg_size_bytes and self.original_size_bytes > 0:
            return round((1 - self.svg_size_bytes / self.original_size_bytes) * 100, 1)
        return 0


class ProductImage(Base):
    """Produktbilder (PNG, JPG - nicht nur SVG-Konvertierungen)"""
    __tablename__ = "product_images"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    # Datei-Informationen
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)  # UUID
    file_path = Column(String(500), nullable=False)  # Relativer Pfad
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(50), nullable=True)  # image/png, image/jpeg
    
    # Bild-Metadaten
    description = Column(String(500), nullable=True)
    is_primary = Column(Integer, default=0)  # 1 = Hauptbild, 0 = Zusatzbild
    sort_order = Column(Integer, default=0)  # Für Reihenfolge
    
    # Verknüpfung mit SVG-Bibliothek (optional)
    converted_file_id = Column(Integer, ForeignKey("converted_files.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Beziehungen
    product = relationship("Product", backref="images")
    converted_file = relationship("ConvertedFile", backref="product_usages")
    
    def __repr__(self):
        return f"ProductImage({self.original_filename} -> Product {self.product_id})"


class ProductComponent(Base):
    """Komponenten für Zusammenbau-Produkte (Assembly)"""
    __tablename__ = "product_components"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    # Komponenten-Details
    name = Column(String(255), nullable=False)  # z.B. "Metall-Ring", "Quaste"
    quantity = Column(Numeric(10, 2), default=1)  # Anzahl dieser Komponente
    unit_cost = Column(Numeric(10, 2), default=0)  # Kosten pro Einheit
    notes = Column(Text, nullable=True)  # Optionale Notizen
    
    # Verknüpfung mit vorhandenem Produkt (optional)
    linked_product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    
    # Sortierung
    sort_order = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Beziehungen
    parent_product = relationship("Product", foreign_keys=[product_id], backref="components")
    linked_product = relationship("Product", foreign_keys=[linked_product_id])
    
    def __repr__(self):
        return f"ProductComponent({self.name} x{self.quantity})"
    
    def calculate_total_cost(self):
        """Berechnet Gesamtkosten für diese Komponente"""
        return float(self.unit_cost) * float(self.quantity)
        return f"ProductComponent({self.name} x{self.quantity})"
    
    def calculate_total_cost(self):
        """Berechnet Gesamtkosten für diese Komponente"""
        return float(self.unit_cost) * float(self.quantity)


class SalesOrderItem(Base):
    """Einzelpositionen eines Verkaufsauftrags (Warenkorb-Positionen)
    
    Kann entweder ein Produkt (selbst hergestellt) oder ein Artikel (eingekauft) sein.
    """
    __tablename__ = "sales_order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    
    # Verknüpfung zum Produkt (selbst hergestellt) - optional
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    
    # Verknüpfung zum Artikel (eingekauft) - optional
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    
    # Menge und Preise
    quantity = Column(Integer, default=1)  # Anzahl verkaufter Einheiten
    unit_price = Column(Numeric(10, 2), nullable=False)  # Verkaufspreis pro Einheit
    
    # Kosten (Kopie zum Zeitpunkt des Verkaufs)
    # Bei Produkt: Produktionskosten, bei Artikel: Einkaufspreis
    cost_per_unit = Column(Numeric(10, 2), default=0)  # Selbstkosten/EK pro Einheit
    
    # Positionstyp für einfache Unterscheidung
    item_type = Column(String(20), default="product")  # 'product' oder 'article'
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Beziehungen
    sales_order = relationship("SalesOrder", backref="items")
    product = relationship("Product", backref="sales_order_items")
    article = relationship("Article", backref="sales_order_items")
    
    def __repr__(self):
        name = self.product.name if self.product else (self.article.name if self.article else "Unknown")
        return f"SalesOrderItem({self.quantity}x {name})"
    
    def get_name(self):
        """Gibt den Namen des Produkts oder Artikels zurück"""
        if self.product:
            return self.product.name
        elif self.article:
            return f"{self.article.article_number} - {self.article.name}"
        return "Unbekannt"
    
    def get_item_link(self):
        """Gibt den Link zum Produkt oder Artikel zurück"""
        if self.product:
            return f"/products/{self.product.id}"
        elif self.article:
            return f"/articles/{self.article.id}"
        return "#"
    
    def calculate_total(self):
        """Berechnet Gesamtsumme für diese Position"""
        return float(self.unit_price) * self.quantity
    
    def calculate_profit(self):
        """Berechnet Gewinn für diese Position"""
        return (float(self.unit_price) - float(self.cost_per_unit)) * self.quantity


class SalesOrder(Base):
    """Verkaufsaufträge - Header mit Kundeninfo und Versandkosten"""
    __tablename__ = "sales_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Verkaufsinformationen
    order_number = Column(String(50), nullable=True)  # Optional: Auftragsnummer
    customer_name = Column(String(255), nullable=True)  # Optional: Kundenname
    
    # Verpackung und Versand (werden hier separat erfasst)
    packaging_cost = Column(Numeric(10, 2), default=0)  # Tatsächliche Verpackungskosten
    shipping_cost = Column(Numeric(10, 2), default=0)  # Tatsächliche Versandkosten
    labor_minutes_packaging = Column(Numeric(10, 2), default=0)  # Arbeitszeit Verpackung (Min)
    labor_rate_packaging = Column(Numeric(10, 2), default=20.00)  # Stundensatz Verpackung (€/h)
    
    # Status
    status = Column(String(20), default="pending")  # 'pending', 'produced', 'shipped', 'cancelled'
    
    # Notizen
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    produced_at = Column(DateTime, nullable=True)  # Wann produziert
    shipped_at = Column(DateTime, nullable=True)  # Wann versendet
    
    def __repr__(self):
        return f"SalesOrder({self.order_number or self.id}: {len(self.items)} Positionen)"
    
    def calculate_items_total(self):
        """Berechnet Summe aller Artikel"""
        return sum(item.calculate_total() for item in self.items)
    
    def calculate_labor_cost(self):
        """Berechnet Arbeitskosten für Verpackung"""
        labor_hours = float(self.labor_minutes_packaging) / 60.0
        return labor_hours * float(self.labor_rate_packaging)
    
    def calculate_total(self):
        """Berechnet Gesamtsumme des Auftrags"""
        items_total = self.calculate_items_total()
        packaging_shipping_labor = float(self.packaging_cost) + float(self.shipping_cost) + self.calculate_labor_cost()
        return items_total + packaging_shipping_labor
    
    def calculate_total_production_cost(self):
        """Berechnet Gesamtkosten aller Artikel inkl. Verpackung/Arbeit"""
        items_cost = sum(float(item.production_cost_per_unit) * item.quantity for item in self.items)
        packaging_shipping_labor = float(self.packaging_cost) + float(self.shipping_cost) + self.calculate_labor_cost()
        return items_cost + packaging_shipping_labor
    
    def calculate_profit(self):
        """Berechnet Gewinn des Auftrags"""
        items_profit = sum(item.calculate_profit() for item in self.items)
        packaging_shipping_labor = float(self.packaging_cost) + float(self.shipping_cost) + self.calculate_labor_cost()
        return items_profit - packaging_shipping_labor
    
    def calculate_margin_percent(self):
        """Berechnet Gewinnmarge in Prozent"""
        total_revenue = self.calculate_items_total()
        if total_revenue == 0:
            return 0.0
        profit = self.calculate_profit()
        return (profit / total_revenue) * 100
    
    def get_total_quantity(self):
        """Gesamtanzahl aller Artikel"""
        return sum(item.quantity for item in self.items)


# =============================================================================
# ARTIKEL-VERWALTUNG
# =============================================================================

class ArticleCategory(Base):
    """Artikelkategorien mit automatischer Nummernvergabe (Präfix-System)"""
    __tablename__ = "article_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), nullable=False, unique=True)  # z.B. 'ART', 'ST', '3D'
    name = Column(String(100), nullable=False)  # z.B. 'Sticker', '3D-Druck'
    description = Column(Text, nullable=True)
    prefix = Column(String(10), nullable=False)  # z.B. 'ART-', 'ST-', '3D-'
    next_number = Column(Integer, default=1)  # Nächste fortlaufende Nummer
    is_active = Column(Integer, default=1)  # 1 = aktiv, 0 = inaktiv
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"ArticleCategory({self.code}: {self.name})"
    
    def generate_article_number(self) -> str:
        """Generiert die nächste Artikelnummer für diese Kategorie"""
        number_str = str(self.next_number).zfill(4)  # 0001, 0002, etc.
        return f"{self.prefix}{number_str}"
    
    def increment_number(self):
        """Erhöht den Nummernzähler"""
        self.next_number += 1


class Article(Base):
    """Artikelstamm - für Waren die eingekauft und weiterverkauft werden
    
    Kann optional mit einem Produkt verknüpft sein, um Produktionskosten zu übernehmen.
    """
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    article_number = Column(String(50), nullable=False, unique=True)  # z.B. 'ART-0001', 'ST-0005'
    
    # Kategorie
    category_id = Column(Integer, ForeignKey("article_categories.id"), nullable=False)
    
    # Optionale Verknüpfung zu einem Produkt (für Selbstkosten-Übernahme)
    linked_product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    
    # Basisdaten
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Preise
    purchase_price = Column(Numeric(10, 2), default=0)  # Einkaufspreis (EK) - bei Produkt-Verknüpfung = Produktionskosten
    selling_price = Column(Numeric(10, 2), default=0)  # Verkaufspreis (VK)
    
    # Lager (optional)
    stock_quantity = Column(Numeric(10, 2), default=0)
    unit = Column(String(20), default="Stück")  # Stück, Meter, kg, Paar, etc.
    
    # Status
    is_active = Column(Integer, default=1)  # 1 = aktiv, 0 = inaktiv
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Beziehungen
    category = relationship("ArticleCategory", backref="articles")
    linked_product = relationship("Product", backref="linked_articles")
    
    def __repr__(self):
        return f"Article({self.article_number}: {self.name})"
    
    def calculate_profit(self) -> float:
        """Berechnet den Gewinn pro Einheit"""
        return float(self.selling_price) - float(self.purchase_price)
    
    def calculate_margin_percent(self) -> float:
        """Berechnet die Gewinnmarge in Prozent"""
        if float(self.selling_price) == 0:
            return 0.0
        return (self.calculate_profit() / float(self.selling_price)) * 100


# =============================================================================
# RECHNUNGS-VERWALTUNG
# =============================================================================

class Invoice(Base):
    """Rechnungen an Kunden"""
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Rechnungsnummer (eindeutig, automatisch generiert)
    invoice_number = Column(String(50), nullable=False, unique=True)
    
    # Verknüpfung zu Verkaufsauftrag (optional)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=True)
    
    # Kundendaten
    customer_name = Column(String(255), nullable=True)
    customer_address = Column(Text, nullable=True)  # Rechnungsadresse
    
    # Daten
    invoice_date = Column(DateTime, default=datetime.utcnow)  # Rechnungsdatum
    due_date = Column(DateTime, nullable=True)  # Fälligkeitsdatum
    
    # Status
    status = Column(String(20), default="draft")  # 'draft', 'sent', 'paid', 'overdue', 'cancelled'
    
    # Beträge
    total_net = Column(Numeric(10, 2), default=0)  # Gesamt netto
    vat_rate = Column(Numeric(5, 2), default=19.00)  # MwSt-Satz (Standard: 19%)
    vat_amount = Column(Numeric(10, 2), default=0)  # MwSt-Betrag
    total_gross = Column(Numeric(10, 2), default=0)  # Gesamt brutto
    
    # Notizen
    notes = Column(Text, nullable=True)  # Interne Notizen
    footer_text = Column(Text, nullable=True)  # Text am Ende der Rechnung
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)  # Wann verschickt
    paid_at = Column(DateTime, nullable=True)  # Wann bezahlt
    
    # Beziehungen
    sales_order = relationship("SalesOrder", backref="invoices")
    
    def __repr__(self):
        return f"Invoice({self.invoice_number}: {self.customer_name or 'Kein Kunde'})"
    
    def calculate_totals(self):
        """Berechnet alle Summen basierend auf den Positionen"""
        total_net = sum(item.total_net for item in self.items)
        vat_amount = total_net * (float(self.vat_rate) / 100)
        total_gross = total_net + vat_amount
        
        self.total_net = round(total_net, 2)
        self.vat_amount = round(vat_amount, 2)
        self.total_gross = round(total_gross, 2)
        
        return {
            'total_net': self.total_net,
            'vat_amount': self.vat_amount,
            'total_gross': self.total_gross
        }


class InvoiceItem(Base):
    """Einzelpositionen einer Rechnung"""
    __tablename__ = "invoice_items"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    
    # Positionsnummer
    position = Column(Integer, nullable=False)  # 1, 2, 3, ...
    
    # Verknüpfung zum Artikel (optional - manuelle Positionen möglich)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    
    # Artikeldaten (Kopie zum Zeitpunkt der Rechnungserstellung)
    article_number = Column(String(50), nullable=True)  # z.B. "ART-0001"
    description = Column(String(500), nullable=False)  # Artikelname/Beschreibung
    
    # Menge und Preis
    quantity = Column(Numeric(10, 2), default=1)
    unit = Column(String(20), default="Stück")
    unit_price_net = Column(Numeric(10, 2), nullable=False)  # Einzelpreis netto
    
    # Gesamtbetrag
    total_net = Column(Numeric(10, 2), nullable=False)  # Menge × Preis
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Beziehungen
    invoice = relationship("Invoice", backref="items")
    article = relationship("Article", backref="invoice_items")
    
    def __repr__(self):
        return f"InvoiceItem({self.position}: {self.description[:30]}...)"
    
    def calculate_total(self):
        """Berechnet den Gesamtbetrag"""
        return float(self.quantity) * float(self.unit_price_net)
