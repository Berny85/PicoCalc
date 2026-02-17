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


class Material(Base):
    """Material-Tabelle für Filamente, Papier, Stickerbögen, etc."""
    __tablename__ = "materials"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    material_type = Column(String(50), nullable=False)  # filament, sticker_sheet, paper, vinyl, etc.
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
        """Kalkulation für Sticker/Papier"""
        costs = {'type': 'sticker_sheet'}
        
        # Materialkosten (Bögen)
        if self.sheet_material_id and self.sheet_material:
            sheet_price = float(self.sheet_material.price_per_unit)
            material_cost = float(self.sheet_count or 0) * sheet_price
            costs['sheet_info'] = f"{self.sheet_material.name}"
        else:
            material_cost = 0
            costs['sheet_info'] = "Kein Material"
        
        costs['material_cost'] = round(material_cost, 2)
        costs['sheet_count'] = float(self.sheet_count or 0)
        
        # Schneidekosten
        machine_cost_per_h = self.get_machine_cost_per_hour()
        cut_cost = float(self.cut_time_hours or 0) * machine_cost_per_h
        costs['machine_cost'] = round(cut_cost, 2)
        costs['machine_cost_per_hour'] = round(machine_cost_per_h, 3)
        costs['cut_time_hours'] = float(self.cut_time_hours or 0)
        
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
        return "Kein Material"
