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
    
    # Kostenparameter
    depreciation_euro = Column(Numeric(10, 2), nullable=False)  # Abschreibung pro Gerät
    lifespan_hours = Column(Numeric(10, 2), nullable=False)  # Lebensdauer in Stunden
    power_kw = Column(Numeric(5, 3), nullable=False)  # Stromverbrauch in kW
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"{self.name} ({self.machine_type})"
    
    def calculate_cost_per_hour(self):
        """Berechnet Maschinenkosten pro Stunde"""
        strom_kosten = STROM_PREIS_KWH * float(self.power_kw)
        abschreibung = float(self.depreciation_euro) / float(self.lifespan_hours)
        return strom_kosten + abschreibung
    
    def calculate_cost_per_unit(self, production_hours):
        """Berechnet Gesamtkosten für Produktionszeit"""
        return production_hours * self.calculate_cost_per_hour()


class MaterialType(Base):
    """Materialtypen - konfigurierbare Liste (Filament, Stickerbogen, etc.)"""
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
    """Material-Tabelle für Filamente, Papier, Stickerbögen, etc."""
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
    
    # === ARBEIT ===
    labor_hours = Column(Numeric(5, 2), default=0)
    labor_rate_per_hour = Column(Numeric(10, 2), default=20.00)
    
    # === KOSTEN ===
    packaging_cost = Column(Numeric(10, 2), default=0)
    shipping_cost = Column(Numeric(10, 2), default=0)
    
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
        
        # Berechnung pro Einheit (Sticker oder Bogen)
        units_per_sheet = float(self.units_per_sheet or 1)
        if units_per_sheet > 0:
            material_cost_per_unit = total_material_cost / units_per_sheet
        else:
            material_cost_per_unit = total_material_cost
        
        costs['material_cost'] = round(material_cost_per_unit, 2)
        costs['total_material_cost'] = round(total_material_cost, 2)
        costs['sheet_count'] = float(self.sheet_count or 0)
        costs['units_per_sheet'] = units_per_sheet
        
        # Keine Maschinenkosten (manuelle Arbeit)
        costs['machine_cost'] = 0
        costs['machine_cost_per_hour'] = 0
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
    
    def calculate_costs(self):
        """Hauptkalkulation je nach Produkttyp"""
        # Typ-spezifische Kosten
        if self.product_type == '3d_print':
            type_costs = self.calculate_3d_print_costs()
            material_cost = type_costs['filament_cost']
            machine_cost = type_costs['machine_cost']
        elif self.product_type in ['sticker_sheet', 'diecut_sticker', 'paper']:
            type_costs = self.calculate_sticker_costs()
            material_cost = type_costs['material_cost']
            machine_cost = type_costs['machine_cost']
        elif self.product_type == 'laser_engraving':
            type_costs = self.calculate_laser_costs()
            material_cost = type_costs['material_cost']
            machine_cost = type_costs['machine_cost']
        else:
            # Generische Berechnung
            type_costs = {'type': 'generic', 'material_cost': 0, 'machine_cost': 0}
            material_cost = 0
            machine_cost = float(self.print_time_hours or 0) * self.get_machine_cost_per_hour()
        
        # Arbeitskosten
        labor_cost = float(self.labor_hours) * float(self.labor_rate_per_hour)
        
        # Gesamtkosten
        total_cost = (material_cost + 
                     machine_cost + 
                     labor_cost + 
                     float(self.packaging_cost) + 
                     float(self.shipping_cost))
        
        result = {
            'material_cost': round(material_cost, 2),
            'machine_cost': round(machine_cost, 2),
            'machine_cost_per_hour': round(self.get_machine_cost_per_hour(), 3),
            'labor_cost': round(labor_cost, 2),
            'labor_hours': float(self.labor_hours),
            'packaging_shipping': round(float(self.packaging_cost) + float(self.shipping_cost), 2),
            'total_cost': round(total_cost, 2),
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
    subject = Column(String(255), nullable=True)  # Betreff-Zeile (optional)
    content = Column(Text, nullable=False)  # Mehrzeiliges Textfeld
    status = Column(String(20), default="todo")  # 'todo', 'in_progress', 'done'
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"Idea({self.subject or self.content[:30]}...)"
