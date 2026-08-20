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
    
    # === FLOHMARKT / EVENT VERFÜGBARKEIT ===
    is_for_market = Column(Integer, default=1, nullable=False)  # 1 = aktiv für Events, 0 = Einmalprodukt/nur Kalkulation
    
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


class MarketEvent(Base):
    """Markt / Flohmarkt / Event für Vorproduktions-Planung"""
    __tablename__ = "market_events"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    event_date = Column(DateTime, nullable=True)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="planning")  # planning, in_production, ready, completed, archived
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Beziehungen mit Kaskadierung
    items = relationship("EventItem", back_populates="event", cascade="all, delete-orphan", order_by="EventItem.sort_order, EventItem.id")
    todos = relationship("EventTodo", back_populates="event", cascade="all, delete-orphan", order_by="EventTodo.sort_order, EventTodo.id")
    
    def __repr__(self):
        return f"MarketEvent({self.id}: {self.name} [{self.status}])"
    
    def calculate_totals(self):
        """Berechnet Gesamtstatistiken, Materialbedarfe und Finanzsummen für dieses Event"""
        total_target_units = 0
        total_produced_units = 0
        total_ek = 0.0
        total_vk = 0.0
        total_print_time_hours = 0.0
        total_labor_minutes = 0.0
        
        filament_breakdown = {}  # {material_name: grams}
        sheet_breakdown = {}     # {material_name: sheets}
        
        for item in self.items:
            target_qty = int(item.target_quantity or 0)
            produced_qty = int(item.produced_quantity or 0)
            total_target_units += target_qty
            total_produced_units += produced_qty
            
            if item.product:
                prod = item.product
                costs = prod.calculate_costs()
                total_ek += float(costs.get('purchase_price', 0)) * target_qty
                total_vk += float(costs.get('selling_price', 0)) * target_qty
                
                # Druckzeit
                if prod.product_type == '3d_print' and prod.print_time_hours:
                    total_print_time_hours += float(prod.print_time_hours) * target_qty
                
                # Arbeitszeit
                if prod.labor_minutes:
                    total_labor_minutes += float(prod.labor_minutes) * target_qty
                
                # Filamentbedarf
                if prod.product_type == '3d_print' and prod.filament_weight_g:
                    mat_name = prod.filament_material.name if prod.filament_material else "Unbekanntes Filament"
                    weight_g = float(prod.filament_weight_g) * target_qty
                    filament_breakdown[mat_name] = filament_breakdown.get(mat_name, 0.0) + weight_g
                
                # Sticker-Bögen-Bedarf
                if prod.product_type in ['sticker', 'sticker_sheet', 'diecut_sticker', 'stationery', 'paper']:
                    mat_name = prod.sheet_material.name if prod.sheet_material else "Unbekannter Stickerbogen"
                    units_per_sheet = float(prod.units_per_sheet or 1)
                    if units_per_sheet > 0:
                        sheets_needed = target_qty / units_per_sheet
                    else:
                        sheets_needed = float(target_qty)
                    sheet_breakdown[mat_name] = sheet_breakdown.get(mat_name, 0.0) + sheets_needed
        
        progress_percent = round((total_produced_units / total_target_units) * 100, 1) if total_target_units > 0 else 0.0
        if progress_percent > 100.0:
            progress_percent = 100.0
            
        todos_total = len(self.todos)
        todos_done = sum(1 for t in self.todos if t.is_done == 1)
        todo_progress_percent = round((todos_done / todos_total) * 100, 1) if todos_total > 0 else 0.0
        
        # Filament gerundet
        formatted_filament = {name: round(weight, 1) for name, weight in filament_breakdown.items()}
        # Bögen gerundet (aufgerundet auf 1 Nachkommastelle bzw. Ganze)
        formatted_sheets = {name: round(sheets, 1) for name, sheets in sheet_breakdown.items()}
        
        return {
            'total_target_units': total_target_units,
            'total_produced_units': total_produced_units,
            'progress_percent': progress_percent,
            'total_ek': round(total_ek, 2),
            'total_vk': round(total_vk, 2),
            'potential_profit': round(total_vk - total_ek, 2),
            'total_print_time_hours': round(total_print_time_hours, 1),
            'total_labor_hours': round(total_labor_minutes / 60.0, 1),
            'total_labor_minutes': round(total_labor_minutes, 0),
            'filament_breakdown': formatted_filament,
            'total_filament_weight_g': round(sum(filament_breakdown.values()), 1),
            'sheet_breakdown': formatted_sheets,
            'total_sheets_count': round(sum(sheet_breakdown.values()), 1),
            'todos_total': todos_total,
            'todos_done': todos_done,
            'todo_progress_percent': todo_progress_percent,
        }


class EventItem(Base):
    """Einzelner Vorproduktions-Artikel innerhalb eines Events"""
    __tablename__ = "event_items"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("market_events.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    custom_name = Column(String(255), nullable=True)  # Falls kein Produkt hinterlegt ist
    target_quantity = Column(Integer, default=1, nullable=False)
    produced_quantity = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Beziehungen
    event = relationship("MarketEvent", back_populates="items")
    product = relationship("Product")
    
    def __repr__(self):
        return f"EventItem({self.get_name()}: {self.produced_quantity}/{self.target_quantity})"
    
    def get_name(self):
        """Gibt den Namen des Artikels zurück"""
        if self.product:
            return self.product.name
        return self.custom_name or "Unbenannter Artikel"
    
    def get_product_type(self):
        """Gibt den Produkttyp zurück"""
        if self.product:
            return self.product.product_type
        return "custom"
    
    def get_progress_percent(self):
        """Berechnet den Fertigstellungsgrad in Prozent"""
        if not self.target_quantity or self.target_quantity <= 0:
            return 100.0 if self.produced_quantity > 0 else 0.0
        pct = round((float(self.produced_quantity) / float(self.target_quantity)) * 100, 1)
        return min(100.0, max(0.0, pct))
    
    def is_completed(self):
        """Prüft, ob die Soll-Menge erreicht wurde"""
        return self.produced_quantity >= self.target_quantity
    
    def get_costs(self):
        """Gibt Kosteninformationen für diesen Artikel zurück"""
        if self.product:
            c = self.product.calculate_costs()
            ek_unit = float(c.get('purchase_price', 0))
            vk_unit = float(c.get('selling_price', 0))
        else:
            ek_unit = 0.0
            vk_unit = 0.0
        
        target_qty = int(self.target_quantity or 0)
        return {
            'ek_unit': round(ek_unit, 2),
            'vk_unit': round(vk_unit, 2),
            'ek_total': round(ek_unit * target_qty, 2),
            'vk_total': round(vk_unit * target_qty, 2),
        }


class EventTodo(Base):
    """Aufgabe / Packlisten-Eintrag für ein Event"""
    __tablename__ = "event_todos"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("market_events.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    category = Column(String(100), default="Allgemein")  # 'Stand & Aufbau', 'Kasse & Finanzen', 'Verpackung & Deko', 'Allgemein'
    is_done = Column(Integer, default=0)  # 0 = offen, 1 = erledigt
    sort_order = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Beziehung
    event = relationship("MarketEvent", back_populates="todos")
    
    def __repr__(self):
        return f"EventTodo({'[x]' if self.is_done else '[ ]'} {self.title})"

