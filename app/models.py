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
    """Materialtypen - konfigurierbare Liste (Filament, Sticker-Sheet, etc.)"""
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
    """Material-Tabelle für Filamente, Papier, Sticker-Sheets, etc."""
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
    product_type = Column(String(50), nullable=False)  # '3d_print', 'sticker', etc.
    category = Column(String(100), default="Sonstiges")
    
    # === 3D-DRUCK SPEZIFISCH ===
    filament_material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    filament_weight_g = Column(Numeric(10, 2), nullable=True)  # Gewicht in Gramm
    print_time_hours = Column(Numeric(5, 2), nullable=True)  # Druckzeit
    
    # === STICKER/PAPIER SPEZIFISCH ===
    sheet_material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    sheet_count = Column(Numeric(10, 2), nullable=True)  # Anzahl Bögen
    cut_time_hours = Column(Numeric(5, 2), nullable=True)  # Schneidezeit
    units_per_sheet = Column(Numeric(10, 2), default=1)  # Wie viele Produkte pro Bogen
    
    # === LASER-GRAVUR SPEZIFISCH (veraltet, bleibt in DB für Kompatibilität) ===
    laser_material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    laser_design_name = Column(String(255), nullable=True)
    laser1_type = Column(String(50), nullable=True)
    laser1_power_percent = Column(Numeric(5, 2), nullable=True)
    laser1_speed_mm_s = Column(Numeric(10, 2), nullable=True)
    laser1_passes = Column(Integer, default=1)
    laser1_dpi = Column(Integer, nullable=True)
    laser1_lines_per_cm = Column(Integer, nullable=True)
    laser2_type = Column(String(50), nullable=True)
    laser2_power_percent = Column(Numeric(5, 2), nullable=True)
    laser2_speed_mm_s = Column(Numeric(10, 2), nullable=True)
    laser2_passes = Column(Integer, nullable=True)
    laser2_dpi = Column(Integer, nullable=True)
    laser2_lines_per_cm = Column(Integer, nullable=True)
    laser3_type = Column(String(50), nullable=True)
    laser3_power_percent = Column(Numeric(5, 2), nullable=True)
    laser3_speed_mm_s = Column(Numeric(10, 2), nullable=True)
    laser3_passes = Column(Integer, nullable=True)
    laser3_dpi = Column(Integer, nullable=True)
    laser3_lines_per_cm = Column(Integer, nullable=True)
    
    # === MASCHINEN ===
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    additional_machine_ids = Column(String(255), nullable=True)  # Kommaseparierte IDs
    
    # === ARBEIT ===
    labor_minutes = Column(Numeric(10, 2), default=0)
    labor_rate_per_hour = Column(Numeric(10, 2), default=20.00)
    
    # === KOSTEN ===
    packaging_cost = Column(Numeric(10, 2), default=0)
    shipping_cost = Column(Numeric(10, 2), default=0)
    
    # === BERECHNUNGSMODUS ===
    calculation_mode = Column(String(20), default="per_unit")
    units_per_batch = Column(Integer, default=1)
    
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
            batch_material_cost = total_material_cost
            batch_machine_cost = total_machine_cost
            batch_size = self.units_per_batch if self.units_per_batch > 0 else 1
            
            material_cost_per_unit = batch_material_cost / batch_size
            machine_cost_per_unit = batch_machine_cost / batch_size
            
            costs['calculation_mode'] = 'per_batch'
            costs['units_per_batch'] = batch_size
            costs['batch_material_cost'] = round(batch_material_cost, 2)
            costs['batch_machine_cost'] = round(batch_machine_cost, 2)
        else:
            units_per_sheet = float(self.units_per_sheet or 1)
            sheet_count_val = float(self.sheet_count or 1)
            total_units = sheet_count_val * units_per_sheet
            
            if total_units > 0:
                material_cost_per_unit = total_material_cost / total_units
            else:
                material_cost_per_unit = total_material_cost
            
            if total_units > 0:
                machine_cost_per_unit = total_machine_cost / total_units
            else:
                machine_cost_per_unit = total_machine_cost
            
            costs['calculation_mode'] = 'per_unit'
            costs['units_per_sheet'] = units_per_sheet
            costs['sheet_count'] = sheet_count_val
            costs['total_units'] = total_units
        
        costs['material_cost'] = round(material_cost_per_unit, 2)
        costs['machine_cost'] = round(machine_cost_per_unit, 2)
        costs['total_material_cost'] = round(total_material_cost, 2)
        costs['cut_time_hours'] = 0
        
        return costs
    
    def calculate_laser_costs(self):
        """Kalkulation für Laser-Gravuren (veraltet, bleibt für Kompatibilität)"""
        costs = {'type': 'laser_engraving'}
        
        if self.laser_material_id and self.laser_material:
            material_price = float(self.laser_material.price_per_unit)
            costs['material_info'] = f"{self.laser_material.name}"
            costs['material_cost'] = round(material_price, 2)
        else:
            costs['material_info'] = "Kein Material"
            costs['material_cost'] = 0
        
        costs['machine_cost'] = 0
        return costs
    
    def calculate_assembly_costs(self):
        """Kalkulation für Zusammenbau-Produkte (veraltet, bleibt für Kompatibilität)"""
        costs = {'type': 'assembly'}
        
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
        costs['machine_cost'] = 0
        
        return costs
    
    def calculate_costs(self):
        """Hauptkalkulation je nach Produkttyp - mit Komponenten-Unterstützung für alle Typen"""
        # Typ-spezifische Kosten
        if self.product_type == '3d_print':
            type_costs = self.calculate_3d_print_costs()
            material_cost = type_costs['filament_cost']
            machine_cost = type_costs['machine_cost']
        elif self.product_type in ['sticker', 'sticker_sheet', 'diecut_sticker', 'stationery', 'paper']:
            type_costs = self.calculate_sticker_costs()
            material_cost = type_costs['material_cost']
            machine_cost = type_costs['machine_cost']
        elif self.product_type == 'laser_engraving':
            type_costs = self.calculate_laser_costs()
            material_cost = type_costs['material_cost']
            machine_cost = type_costs['machine_cost']
        elif self.product_type == 'assembly':
            type_costs = self.calculate_assembly_costs()
            material_cost = type_costs['material_cost']  # Enthält bereits Komponenten
            machine_cost = type_costs['machine_cost']
        else:
            type_costs = {'type': 'generic', 'material_cost': 0, 'machine_cost': 0}
            material_cost = 0
            machine_cost = float(self.print_time_hours or 0) * self.get_machine_cost_per_hour()
        
        # Komponenten-Kosten (für alle Produkttypen außer assembly, wo sie bereits in material_cost enthalten sind)
        components_cost = 0.0
        components_details = []
        if self.product_type != 'assembly':
            for component in self.components:
                comp_cost = component.calculate_total_cost()
                components_cost += comp_cost
                components_details.append({
                    'name': component.name,
                    'quantity': float(component.quantity),
                    'unit_cost': float(component.unit_cost),
                    'total': round(comp_cost, 2),
                    'notes': component.notes,
                    'linked_product_id': component.linked_product_id
                })
        
        # Arbeitskosten (labor_minutes ist in Minuten, daher / 60 für Stunden)
        labor_hours = float(self.labor_minutes) / 60.0
        labor_cost = labor_hours * float(self.labor_rate_per_hour)
        labor_cost_batch = None
        
        # Bei per_batch: Arbeitskosten auf Einheit umrechnen
        if self.calculation_mode == 'per_batch' and self.units_per_batch > 0:
            labor_cost_per_unit = labor_cost / self.units_per_batch
            labor_cost_batch = labor_cost
            labor_cost = labor_cost_per_unit
        elif self.product_type in ['sticker', 'sticker_sheet', 'diecut_sticker', 'stationery', 'paper'] and self.calculation_mode == 'per_unit':
            # Für Bogen-basierte Produkte: Arbeitskosten pro Bogen auf Einheit umrechnen
            total_units = float(self.sheet_count or 1) * float(self.units_per_sheet or 1)
            if total_units > 0:
                labor_cost = labor_cost / total_units
        
        # Verpackung/Versand
        packaging_cost = float(self.packaging_cost)
        shipping_cost = float(self.shipping_cost)
        
        # Gesamtkosten (Einkaufspreis / Selbstkosten)
        total_cost = material_cost + machine_cost + labor_cost + components_cost + packaging_cost + shipping_cost
        
        # Verkaufspreis (100% Aufschlag = doppelter EK)
        selling_price = total_cost * 2.0
        
        result = {
            'material_cost': round(material_cost, 2),
            'machine_cost': round(machine_cost, 2),
            'machine_cost_per_hour': round(self.get_machine_cost_per_hour(), 3),
            'labor_cost': round(labor_cost, 2),
            'labor_hours': labor_hours,
            'labor_minutes': float(self.labor_minutes),
            'labor_cost_batch': round(labor_cost_batch, 2) if self.calculation_mode == 'per_batch' else None,
            'components_cost': round(components_cost, 2),
            'components': components_details,
            'components_count': len(components_details),
            'packaging_cost': packaging_cost,
            'shipping_cost': shipping_cost,
            'packaging_shipping': round(packaging_cost + shipping_cost, 2),
            'total_cost': round(total_cost, 2),
            'purchase_price': round(total_cost, 2),
            'selling_price': round(selling_price, 2),
            'calculation_mode': self.calculation_mode,
            'units_per_batch': self.units_per_batch if self.calculation_mode == 'per_batch' else None,
        }
        
        # Typ-spezifische Details hinzufügen
        result.update(type_costs)
        
        return result
    
    def get_material_summary(self):
        """Zusammenfassung des verwendeten Materials"""
        if self.product_type == '3d_print' and self.filament_material:
            return f"{self.filament_weight_g}g {self.filament_material.name}"
        elif self.product_type in ['sticker', 'sticker_sheet', 'diecut_sticker', 'paper'] and self.sheet_material:
            return f"{self.sheet_count} {self.sheet_material.unit} {self.sheet_material.name}"
        elif self.product_type == 'laser_engraving':
            if self.laser_material:
                return f"{self.laser_material.name}"
            return "Kein Material angegeben"
        return "Kein Material"


class ProductComponent(Base):
    """Komponenten für Produkte (z.B. Metall-Ring, Anhänger, etc.)"""
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


class FeedbackIdea(Base):
    """Feedback und Ideen-Verwaltung"""
    __tablename__ = "feedback_ideas"
    
    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='open')  # 'open' oder 'done'
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"FeedbackIdea({self.status}: {self.description[:50]})"   


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
    
    # Konvertierungs-Optionen (fuer Dokumentation/Re-Konvertierung)
    conversion_mode = Column(String(50), default="spline")  # 'spline' oder 'pixel'
    color_mode = Column(String(50), default="color")  # 'color' oder 'binary'
    
    # Optional: Beschreibung/Tags fuer die Suche
    description = Column(String(500), nullable=True)
    tags = Column(String(255), nullable=True)  # Komma-getrennte Tags
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"ConvertedFile({self.original_filename})"
    
    def get_size_reduction_percent(self):
        """Berechnet die Groessenreduktion in Prozent"""
        if self.original_size_bytes and self.svg_size_bytes and self.original_size_bytes > 0:
            return round((1 - self.svg_size_bytes / self.original_size_bytes) * 100, 1)
        return 0
