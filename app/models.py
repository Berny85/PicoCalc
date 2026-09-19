from math import ceil

from sqlalchemy import (
    Column, Integer, String, Numeric, Text, DateTime, ForeignKey, Boolean, CheckConstraint, select,
)
from sqlalchemy.orm import relationship, object_session, column_property
from database import Base
from datetime import datetime

import calc
from calc import (
    CalcSettings, LaborInput, MachineInput, MaterialInput, ProductInput, BILLING_TIME, BILLING_SHEET, dec
)
from units import input_label

# Fallback, falls in der Config noch kein Strompreis hinterlegt ist
STROM_PREIS_KWH = 0.22  # €/kWh Default


def load_calc_settings(session) -> CalcSettings:
    """Liest Strompreis und Marge aus der Config-Tabelle (mit Fallback auf die Standardwerte)."""
    values = {}
    if session is not None:
        rows = session.query(Config).filter(
            Config.key.in_(["electricity_price_kwh", "margin_multiplier"])
        ).all()
        values = {r.key: r.value for r in rows}

    def read(key, default):
        try:
            return dec(values.get(key), default)
        except Exception:
            return default

    return CalcSettings(
        electricity_price_kwh=read("electricity_price_kwh", calc.DEFAULT_ELECTRICITY_PRICE),
        margin_multiplier=read("margin_multiplier", calc.DEFAULT_MARGIN),
    )


def machine_type_label(machines) -> str:
    """Typ-Bezeichnung eines Produkts aus seinen Maschinen (ohne Maschine: „Handarbeit“)."""
    names = []
    for machine in machines:
        name = machine.machine_type.name
        if name not in names:
            names.append(name)
    return " + ".join(names) if names else "Handarbeit"



class MachineType(Base):
    """Maschinentypen (3D-Drucker, Schneideplotter, ...). Der Typ ist nur ein Etikett; wie eine
    Maschine abrechnet, steht an der Maschine selbst (``billing_mode``). ``default_billing_mode``
    dient lediglich als Vorbelegung beim Anlegen einer neuen Maschine."""
    __tablename__ = "machine_types"
    __table_args__ = (
        CheckConstraint("default_billing_mode IN ('time', 'sheet')", name="ck_machine_types_billing_mode"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    default_billing_mode = Column(String(10), nullable=False, default=BILLING_TIME)
    sort_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return self.name


class Machine(Base):
    """Maschinen (Drucker, Plotter, ...)"""
    __tablename__ = "machines"
    __table_args__ = (
        CheckConstraint("billing_mode IN ('time', 'sheet')", name="ck_machines_billing_mode"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    machine_type_id = Column(Integer, ForeignKey("machine_types.id"), nullable=False)
    # 'time': Nutzung in Minuten, Kosten über Stundensatz; 'sheet': Nutzung in Bögen, Kosten pro Bogen
    billing_mode = Column(String(10), nullable=False, default=BILLING_TIME)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    machine_type = relationship("MachineType")
    # Die Kostenparameter liegen in eigenen 1:1-Tabellen. Zeitkosten sind bei Abrechnung nach Zeit Pflicht
    # (bei Bogen-Maschinen optional, dienen dort nur der Herleitung des Bogenpreises); der Bogenpreis ist bei
    # Abrechnung pro Bogen Pflicht.
    time_costs = relationship("MachineTimeCost", uselist=False, back_populates="machine", cascade="all, delete-orphan")
    sheet_costs = relationship("MachineSheetCost", uselist=False, back_populates="machine", cascade="all, delete-orphan")

    def __repr__(self):
        return f"{self.name} ({self.billing_mode})"

    # ---- Kostenparameter (Zugriff wie bisher, Werte ohne Datensatz: 0 bzw. 1 Stunde) -----------------

    @property
    def depreciation_euro(self):
        return dec(self.time_costs.depreciation_euro) if self.time_costs else dec(0)

    @property
    def lifespan_hours(self):
        return dec(self.time_costs.lifespan_hours) if self.time_costs else dec(1)

    @property
    def power_w(self):
        return dec(self.time_costs.power_w) if self.time_costs else dec(0)

    @property
    def cost_per_sheet(self):
        return dec(self.sheet_costs.cost_per_sheet) if self.sheet_costs else None

    def set_time_costs(self, depreciation_euro, lifespan_hours, power_w):
        if self.time_costs is None:
            self.time_costs = MachineTimeCost()
        self.time_costs.depreciation_euro = depreciation_euro
        self.time_costs.lifespan_hours = lifespan_hours
        self.time_costs.power_w = power_w

    def set_sheet_cost(self, cost_per_sheet):
        """Bogenpreis setzen; ``None`` entfernt den Datensatz."""
        if cost_per_sheet is None:
            self.sheet_costs = None
        elif self.sheet_costs is None:
            self.sheet_costs = MachineSheetCost(cost_per_sheet=cost_per_sheet)
        else:
            self.sheet_costs.cost_per_sheet = cost_per_sheet

    def cost_per_hour(self, electricity_price=None):
        """Stundensatz (Strom + Abschreibung) als Decimal"""
        if electricity_price is None:
            electricity_price = load_calc_settings(object_session(self)).electricity_price_kwh
        return calc.machine_cost_per_hour(
            self.depreciation_euro, self.lifespan_hours, self.power_w, electricity_price
        )

    def cost_per_sheet_value(self):
        """Preis pro Bogen als Decimal (0, falls nicht hinterlegt)"""
        return dec(self.cost_per_sheet)

    def usage_unit_label(self):
        return "Bögen" if self.billing_mode == BILLING_SHEET else "Minuten"

    def to_input(self, value) -> MachineInput:
        return MachineInput(
            machine_id=self.id, name=self.name, billing_mode=self.billing_mode, value=dec(value),
            depreciation_euro=dec(self.depreciation_euro), lifespan_hours=dec(self.lifespan_hours),
            power_w=dec(self.power_w), cost_per_sheet=dec(self.cost_per_sheet),
        )


class MachineTimeCost(Base):
    """Zeitbasierte Kosten einer Maschine: Abschreibung über die Lebensdauer plus Strom."""
    __tablename__ = "machine_time_costs"
    __table_args__ = (
        CheckConstraint("lifespan_hours > 0", name="ck_machine_time_costs_lifespan"),
        CheckConstraint("depreciation_euro >= 0 AND power_w >= 0", name="ck_machine_time_costs_nonnegative"),
    )

    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"), primary_key=True)
    depreciation_euro = Column(Numeric(12, 2), nullable=False, default=0)   # Anschaffungskosten/Abschreibung
    lifespan_hours = Column(Numeric(10, 2), nullable=False, default=1)      # Lebensdauer in Stunden
    power_w = Column(Numeric(8, 1), nullable=False, default=0)              # Stromverbrauch in Watt

    machine = relationship("Machine", back_populates="time_costs")


class MachineSheetCost(Base):
    """Bogenpreis einer Maschine (pauschale Kosten pro Bogen/Durchlauf)."""
    __tablename__ = "machine_sheet_costs"
    __table_args__ = (
        CheckConstraint("cost_per_sheet >= 0", name="ck_machine_sheet_costs_nonnegative"),
    )

    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"), primary_key=True)
    cost_per_sheet = Column(Numeric(12, 4), nullable=False)

    machine = relationship("Machine", back_populates="sheet_costs")


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


class Brand(Base):
    """Marken/Hersteller von Materialien (Prusament, Xerox, ...)"""
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return self.name


class Material(Base):
    """Materialien: Filamente, Papier, Sticker-Sheets, Kleinteile, ...

    Der Preis steht nicht am Material, sondern in ``material_prices`` (Historie). ``price_per_unit`` ist
    der jeweils aktuelle (neueste) Preis und nur lesbar; ändern über ``set_price``."""
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    material_type_id = Column(Integer, ForeignKey("material_types.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id", ondelete="SET NULL"), nullable=True)
    color = Column(String(50), nullable=True)
    unit = Column(String(20), nullable=False)  # Schlüssel aus units.MATERIAL_UNITS
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    material_type = relationship("MaterialType")
    brand = relationship("Brand")
    prices = relationship(
        "MaterialPrice", back_populates="material", cascade="all, delete-orphan",
        order_by="desc(MaterialPrice.valid_from), desc(MaterialPrice.id)",
    )

    def __repr__(self):
        return f"{self.name} ({self.unit})"

    @property
    def brand_name(self) -> str:
        return self.brand.name if self.brand else ""

    @property
    def input_label(self):
        """Einheit, in der die Menge im Produkt erfasst wird (z.B. Gramm bei kg-Preis)"""
        return input_label(self.unit)

    def set_price(self, price) -> None:
        """Neuen Preis eintragen; bleibt der Preis gleich, entsteht kein neuer Historieneintrag."""
        latest = self.prices[0] if self.prices else None
        if latest is None or dec(latest.price) != dec(price):
            self.prices.append(MaterialPrice(price=price))

    def to_input(self, amount) -> MaterialInput:
        return MaterialInput(
            material_id=self.id, name=self.name, unit=self.unit, amount=dec(amount),
            price_per_unit=dec(self.price_per_unit),
        )


class MaterialPrice(Base):
    """Preis eines Materials pro Preis-Einheit (z.B. €/kg) ab einem Zeitpunkt. Der neueste Eintrag gilt."""
    __tablename__ = "material_prices"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_material_prices_nonnegative"),
    )

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    price = Column(Numeric(12, 4), nullable=False)
    valid_from = Column(DateTime, nullable=False, default=datetime.utcnow)

    material = relationship("Material", back_populates="prices")


# Aktueller Preis als schreibgeschützte Spalte (ein Subselect, dadurch auch sortierbar/filterbar)
Material.price_per_unit = column_property(
    select(MaterialPrice.price)
    .where(MaterialPrice.material_id == Material.id)
    .order_by(MaterialPrice.valid_from.desc(), MaterialPrice.id.desc())
    .limit(1)
    .correlate_except(MaterialPrice)
    .scalar_subquery()
)


class Product(Base):
    """Produkt = Rezept für eine Charge (Materialien + Maschinen + Arbeit) und die Ausbeute."""
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("yield_qty >= 1", name="ck_products_yield_min"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    notes = Column(Text, nullable=True)

    # Wie viele Verkaufseinheiten entstehen aus einer Charge
    yield_qty = Column(Integer, nullable=False, default=1)

    # Pro Stück
    shipping_cost = Column(Numeric(12, 4), nullable=False, default=0)    # nur Richtwert, fließt nicht in die Kalkulation
    selling_price = Column(Numeric(12, 2), nullable=True)                # manueller VK (sonst Richtwert)

    is_for_market = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    material_links = relationship(
        "ProductMaterial", back_populates="product", cascade="all, delete-orphan",
        order_by="ProductMaterial.sort_order",
    )
    machine_links = relationship(
        "ProductMachine", back_populates="product", cascade="all, delete-orphan",
        order_by="ProductMachine.sort_order",
    )
    labor_steps = relationship(
        "ProductLabor", back_populates="product", cascade="all, delete-orphan",
        order_by="ProductLabor.sort_order",
    )
    packaging_links = relationship(
        "ProductPackaging", back_populates="product", cascade="all, delete-orphan",
        order_by="ProductPackaging.sort_order",
    )

    def __repr__(self):
        return f"Product({self.id}: {self.name})"

    @property
    def labor_minutes(self):
        """Gesamte Arbeitszeit einer Charge in Minuten (Summe der Arbeitsschritte)"""
        return sum((dec(step.minutes) for step in self.labor_steps), dec(0))

    # ---- Kalkulation -------------------------------------------------------------------

    def to_input(self) -> ProductInput:
        return ProductInput(
            yield_qty=self.yield_qty or 1,
            selling_price=dec(self.selling_price) if self.selling_price is not None else None,
            materials=tuple(l.material.to_input(l.amount) for l in self.material_links),
            machines=tuple(l.machine.to_input(l.value) for l in self.machine_links),
            labor=tuple(
                LaborInput(minutes=dec(s.minutes), hourly_rate=dec(s.hourly_rate), description=s.description or "")
                for s in self.labor_steps
            ),
            packaging=tuple(l.material.to_input(l.amount) for l in self.packaging_links),
        )

    def calculate(self, settings: CalcSettings | None = None) -> calc.ProductCosts:
        if settings is None:
            settings = load_calc_settings(object_session(self))
        return calc.calculate_product(self.to_input(), settings)

    def calculate_costs(self, settings: CalcSettings | None = None) -> dict:
        """Kalkulation als flaches Dict für Templates (Beträge auf Cent gerundet)"""
        return calc.costs_to_view(self.calculate(settings), shipping_cost=dec(self.shipping_cost))

    # ---- Anzeige -----------------------------------------------------------------------

    @property
    def type_label(self) -> str:
        """Typ des Produkts, abgeleitet aus den verwendeten Maschinen"""
        return machine_type_label(link.machine for link in self.machine_links)

    def get_material_summary(self) -> str:
        if not self.material_links:
            return "Kein Material"
        return ", ".join(
            f"{l.amount:g} {l.material.input_label} {l.material.name}" for l in self.material_links
        )

    def get_machine_summary(self) -> str:
        if not self.machine_links:
            return "Keine Maschine"
        return ", ".join(
            f"{l.machine.name} ({l.value:g} {l.machine.usage_unit_label()})" for l in self.machine_links
        )


class ProductMaterial(Base):
    """Material einer Charge: Menge in der Eingabe-Einheit des Materials (z.B. Gramm bei kg-Preis)."""
    __tablename__ = "product_materials"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    amount = Column(Numeric(14, 3), nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="material_links")
    material = relationship("Material")


class ProductMachine(Base):
    """Maschinennutzung einer Charge: Minuten (billing_mode 'time') bzw. Bögen ('sheet')."""
    __tablename__ = "product_machines"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    value = Column(Numeric(10, 2), nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="machine_links")
    machine = relationship("Machine")


class ProductLabor(Base):
    """Arbeitsschritt einer Charge (z.B. „Stützen entfernen“) mit eigener Zeit und eigenem Stundensatz."""
    __tablename__ = "product_labor"
    __table_args__ = (
        CheckConstraint("minutes >= 0 AND hourly_rate >= 0", name="ck_product_labor_nonnegative"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(255), nullable=True)
    minutes = Column(Numeric(10, 2), nullable=False, default=0)
    hourly_rate = Column(Numeric(10, 2), nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="labor_steps")


class ProductPackaging(Base):
    """Verpackungsmaterial pro Verkaufseinheit (z.B. 1 Beutel, 1 Karte). Wird ohne Marge durchgereicht;
    die Menge gilt pro Stück und nicht pro Charge."""
    __tablename__ = "product_packaging"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    amount = Column(Numeric(14, 3), nullable=False, default=1)
    sort_order = Column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="packaging_links")
    material = relationship("Material")


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
    product_ideas = Column(Text, nullable=True)  # Freitext für Produkt-Ideen & Chat-Brainstorming
    status = Column(String(50), nullable=False, default="planning")  # planning, in_production, ready, completed, archived

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Beziehungen mit Kaskadierung
    items = relationship("EventItem", back_populates="event", cascade="all, delete-orphan", order_by="EventItem.sort_order, EventItem.id")
    todos = relationship("EventTodo", back_populates="event", cascade="all, delete-orphan", order_by="EventTodo.sort_order, EventTodo.id")

    def __repr__(self):
        return f"MarketEvent({self.id}: {self.name} [{self.status}])"

    def calculate_totals(self, settings: CalcSettings | None = None):
        """Gesamtstatistiken, Materialbedarf und Finanzsummen für dieses Event.

        Der Bedarf wird in ganzen Chargen gerechnet: Für 8 Stück bei Ausbeute 3 sind 3 Chargen
        nötig, also 3 x Materialmenge, 3 x Maschinenzeit und 3 x Arbeitszeit der Charge."""
        if settings is None:
            settings = load_calc_settings(object_session(self))

        total_target_units = 0
        total_produced_units = 0
        total_ek = 0.0
        total_vk = 0.0
        total_machine_minutes = 0.0
        total_machine_sheets = 0.0
        total_labor_minutes = 0.0

        filament_breakdown = {}  # Materialien mit kg-Preis: {name: Gramm}
        sheet_breakdown = {}     # Materialien mit Bogen-Preis: {name: Bögen}
        other_breakdown = {}     # Übrige Materialien: {(name, Einheit): Menge}

        for item in self.items:
            target_qty = int(item.target_quantity or 0)
            produced_qty = int(item.produced_quantity or 0)
            total_target_units += target_qty
            total_produced_units += produced_qty

            item_costs = item.get_costs(settings)
            total_ek += item_costs['ek_total']
            total_vk += item_costs['vk_total']

            prod = item.product
            if not prod or target_qty <= 0:
                continue

            batches = ceil(target_qty / max(1, prod.yield_qty or 1))

            total_labor_minutes += float(prod.labor_minutes or 0) * batches

            for link in prod.machine_links:
                amount = float(link.value or 0) * batches
                if link.machine.billing_mode == BILLING_SHEET:
                    total_machine_sheets += amount
                else:
                    total_machine_minutes += amount

            for link in prod.material_links:
                mat = link.material
                amount = float(link.amount or 0) * batches
                if mat.unit == "kg":
                    filament_breakdown[mat.name] = filament_breakdown.get(mat.name, 0.0) + amount
                elif mat.unit == "sheet":
                    sheet_breakdown[mat.name] = sheet_breakdown.get(mat.name, 0.0) + amount
                else:
                    key = (mat.name, mat.input_label)
                    other_breakdown[key] = other_breakdown.get(key, 0.0) + amount

        progress_percent = round((total_produced_units / total_target_units) * 100, 1) if total_target_units > 0 else 0.0
        if progress_percent > 100.0:
            progress_percent = 100.0

        todos_total = len(self.todos)
        todos_done = sum(1 for t in self.todos if t.is_done == 1)
        todo_progress_percent = round((todos_done / todos_total) * 100, 1) if todos_total > 0 else 0.0

        return {
            'total_target_units': total_target_units,
            'total_produced_units': total_produced_units,
            'progress_percent': progress_percent,
            'total_ek': round(total_ek, 2),
            'total_vk': round(total_vk, 2),
            'potential_profit': round(total_vk - total_ek, 2),
            # "print_time" heißt aus Kompatibilität zu den Templates so, gemeint ist die gesamte Maschinenzeit
            'total_print_time_hours': round(total_machine_minutes / 60.0, 1),
            'total_machine_sheets': round(total_machine_sheets, 1),
            'total_labor_hours': round(total_labor_minutes / 60.0, 1),
            'total_labor_minutes': round(total_labor_minutes, 0),
            'filament_breakdown': {n: round(w, 1) for n, w in filament_breakdown.items()},
            'total_filament_weight_g': round(sum(filament_breakdown.values()), 1),
            'sheet_breakdown': {n: round(s, 1) for n, s in sheet_breakdown.items()},
            'total_sheets_count': round(sum(sheet_breakdown.values()), 1),
            'other_breakdown': [
                {'name': n, 'unit': u, 'amount': round(a, 1)} for (n, u), a in other_breakdown.items()
            ],
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
    custom_vk = Column(Numeric(10, 2), nullable=True)  # Individueller Flohmarkt-VK pro Stück
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
        """Gibt den Typ des Artikels zurück (aus den Maschinen des Produkts abgeleitet)"""
        if self.product:
            return self.product.type_label
        return "Eigener Artikel"

    def get_progress_percent(self):
        """Berechnet den Fertigstellungsgrad in Prozent"""
        if not self.target_quantity or self.target_quantity <= 0:
            return 100.0 if self.produced_quantity > 0 else 0.0
        pct = round((float(self.produced_quantity) / float(self.target_quantity)) * 100, 1)
        return min(100.0, max(0.0, pct))

    def is_completed(self):
        """Prüft, ob die Soll-Menge erreicht wurde"""
        return self.produced_quantity >= self.target_quantity

    def get_costs(self, settings: CalcSettings | None = None):
        """Gibt Kosteninformationen für diesen Artikel zurück"""
        if self.product:
            c = self.product.calculate_costs(settings)
            ek_unit = float(c.get('purchase_price', 0))
            default_vk = float(c.get('selling_price', 0))
        else:
            ek_unit = 0.0
            default_vk = 0.0

        # Individuellen Flohmarkt-VK nutzen falls gesetzt und > 0
        if self.custom_vk is not None and float(self.custom_vk) > 0:
            vk_unit = float(self.custom_vk)
            is_custom_vk = True
        else:
            vk_unit = default_vk
            is_custom_vk = False

        target_qty = int(self.target_quantity or 0)
        return {
            'ek_unit': round(ek_unit, 2),
            'vk_unit': round(vk_unit, 2),
            'default_vk': round(default_vk, 2),
            'custom_vk': float(self.custom_vk) if self.custom_vk is not None else None,
            'is_custom_vk': is_custom_vk,
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


class Config(Base):
    """Konfigurations-Tabelle für globale Einstellungen (Key-Value Store für einzelne Werte)"""
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True)  # z.B. 'electricity_price_kwh'
    value = Column(Text, nullable=True)  # Der Wert als Text
    description = Column(String(255), nullable=True)  # Beschreibung für UI
    category = Column(String(50), default="general")  # 'general', 'pricing', etc.

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"Config({self.key}={self.value[:30] if self.value else 'None'}...)"
