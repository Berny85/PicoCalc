"""Kalkulation eines Produkts - reine Funktionen ohne Datenbankzugriff.

Ein Produkt beschreibt eine *Charge*: Materialien, Maschinenzeiten und Arbeitszeit ergeben die
Chargenkosten, geteilt durch die Ausbeute ergeben sich die Herstellkosten pro Stück. Die Verpackung
wird pro Stück 1:1 aufgeschlagen (ohne Marge).

Gerechnet wird durchgehend mit ``Decimal`` und ohne Zwischenrundung; gerundet wird erst für die
Anzeige (``money``).
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from units import unit_factor

ZERO = Decimal(0)
CENT = Decimal("0.01")

BILLING_TIME = "time"    # Nutzung in Minuten, Kosten über Stundensatz der Maschine
BILLING_SHEET = "sheet"  # Nutzung in Bögen/Durchläufen, Kosten über Preis pro Bogen
BILLING_MODES = (BILLING_TIME, BILLING_SHEET)

DEFAULT_ELECTRICITY_PRICE = Decimal("0.22")
DEFAULT_MARGIN = Decimal("2.0")


def dec(value, default=ZERO) -> Decimal:
    """Wandelt Zahlen/Strings (auch mit Komma) sicher in Decimal um."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    text = str(value).strip().replace(",", ".")
    if text == "":
        return default
    return Decimal(text)


def money(value) -> Decimal:
    """Auf Cent gerundet (nur für die Anzeige gedacht)."""
    return dec(value).quantize(CENT, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------- Eingaben

@dataclass(frozen=True)
class MaterialInput:
    material_id: int
    name: str
    unit: str
    amount: Decimal           # Eingabe-Einheit pro Charge (z.B. Gramm)
    price_per_unit: Decimal   # Preis pro Preis-Einheit (z.B. €/kg)


@dataclass(frozen=True)
class MachineInput:
    machine_id: int
    name: str
    billing_mode: str
    value: Decimal            # Minuten (time) bzw. Bögen (sheet) pro Charge
    depreciation_euro: Decimal = ZERO
    lifespan_hours: Decimal = Decimal(1)
    power_w: Decimal = ZERO
    cost_per_sheet: Decimal = ZERO


@dataclass(frozen=True)
class LaborInput:
    minutes: Decimal          # pro Charge
    hourly_rate: Decimal
    description: str = ""


@dataclass(frozen=True)
class ProductInput:
    yield_qty: int = 1
    selling_price: Decimal | None = None
    materials: tuple[MaterialInput, ...] = ()
    machines: tuple[MachineInput, ...] = ()
    labor: tuple[LaborInput, ...] = ()
    packaging: tuple[MaterialInput, ...] = ()   # Menge pro Verkaufseinheit (nicht pro Charge), ohne Marge


@dataclass(frozen=True)
class CalcSettings:
    electricity_price_kwh: Decimal = DEFAULT_ELECTRICITY_PRICE
    margin_multiplier: Decimal = DEFAULT_MARGIN


# --------------------------------------------------------------------------- Einzelkosten

def machine_rate_breakdown(depreciation_euro, lifespan_hours, power_w, electricity_price_kwh) -> tuple[Decimal, Decimal, Decimal]:
    """Stundensatz einer Maschine als (gesamt, Strom, Abschreibung) in €/h."""
    lifespan = dec(lifespan_hours)
    if lifespan <= 0:
        lifespan = Decimal(1)
    strom = dec(power_w) / 1000 * dec(electricity_price_kwh)
    abschreibung = dec(depreciation_euro) / lifespan
    return strom + abschreibung, strom, abschreibung


def machine_cost_per_hour(depreciation_euro, lifespan_hours, power_w, electricity_price_kwh) -> Decimal:
    """Stundensatz einer Maschine: Strom + Abschreibung."""
    return machine_rate_breakdown(depreciation_euro, lifespan_hours, power_w, electricity_price_kwh)[0]


MIN_SHEET_PRICE = Decimal("0.08")


def sheet_cost_estimate(rate_per_hour, minutes_per_sheet, wear_cost) -> tuple[Decimal, Decimal]:
    """Herleitung der Mindestkosten pro Bogen: (reine Maschinenkosten, inkl. Verschleiß)."""
    machine = dec(rate_per_hour) / 60 * dec(minutes_per_sheet)
    return machine, machine + dec(wear_cost)


def recommended_sheet_price(min_cost) -> Decimal:
    """Empfohlener Bogenpreis: auf volle Cent aufgerundet, mindestens 0,08 €."""
    rounded = (dec(min_cost) * 100).to_integral_value(rounding=ROUND_CEILING) / 100
    return max(rounded, MIN_SHEET_PRICE)


def material_cost(amount, price_per_unit, unit: str) -> Decimal:
    """Kosten einer Materialmenge (Menge in Eingabe-Einheit, Preis pro Preis-Einheit)."""
    return dec(amount) / unit_factor(unit) * dec(price_per_unit)


def machine_cost(machine: MachineInput, electricity_price_kwh) -> Decimal:
    if machine.billing_mode == BILLING_SHEET:
        return machine.value * machine.cost_per_sheet
    rate = machine_cost_per_hour(machine.depreciation_euro, machine.lifespan_hours,
                                 machine.power_w, electricity_price_kwh)
    return machine.value / 60 * rate


# --------------------------------------------------------------------------- Ergebnis

@dataclass(frozen=True)
class MaterialLine:
    material_id: int
    name: str
    unit: str
    amount: Decimal
    price_per_unit: Decimal
    cost: Decimal


@dataclass(frozen=True)
class MachineLine:
    machine_id: int
    name: str
    billing_mode: str
    value: Decimal
    rate: Decimal   # €/h (time) bzw. €/Bogen (sheet)
    cost: Decimal


@dataclass(frozen=True)
class LaborLine:
    description: str
    minutes: Decimal
    hourly_rate: Decimal
    cost: Decimal


@dataclass(frozen=True)
class ProductCosts:
    materials: tuple[MaterialLine, ...]
    machines: tuple[MachineLine, ...]
    labor: tuple[LaborLine, ...]
    packaging: tuple[MaterialLine, ...]
    yield_qty: int

    # Chargenkosten
    material_total: Decimal
    machine_total: Decimal
    labor_total: Decimal
    batch_total: Decimal

    # pro Stück
    material_per_unit: Decimal
    machine_per_unit: Decimal
    labor_per_unit: Decimal
    production_cost: Decimal      # Herstellkosten ohne Verpackung
    packaging_cost: Decimal
    total_cost: Decimal           # Selbstkosten (EK) inkl. Verpackung
    recommended_price: Decimal    # Herstellkosten * Marge + Verpackung
    selling_price: Decimal        # manueller VK, sonst Richtwert
    has_custom_price: bool
    profit: Decimal
    margin_percent: Decimal       # Gewinn / VK in %


def calculate_product(product: ProductInput, settings: CalcSettings | None = None) -> ProductCosts:
    settings = settings or CalcSettings()
    yield_qty = max(1, int(product.yield_qty or 1))

    def material_lines_for(items):
        return tuple(
            MaterialLine(
                material_id=m.material_id, name=m.name, unit=m.unit, amount=m.amount,
                price_per_unit=m.price_per_unit,
                cost=material_cost(m.amount, m.price_per_unit, m.unit),
            )
            for m in items
        )

    material_lines = material_lines_for(product.materials)
    packaging_lines = material_lines_for(product.packaging)
    labor_lines = tuple(
        LaborLine(description=step.description, minutes=step.minutes, hourly_rate=step.hourly_rate,
                  cost=step.minutes / 60 * step.hourly_rate)
        for step in product.labor
    )

    machine_lines = []
    for m in product.machines:
        if m.billing_mode == BILLING_SHEET:
            rate = m.cost_per_sheet
        else:
            rate = machine_cost_per_hour(m.depreciation_euro, m.lifespan_hours, m.power_w,
                                         settings.electricity_price_kwh)
        machine_lines.append(MachineLine(
            machine_id=m.machine_id, name=m.name, billing_mode=m.billing_mode, value=m.value,
            rate=rate, cost=machine_cost(m, settings.electricity_price_kwh),
        ))

    material_total = sum((line.cost for line in material_lines), ZERO)
    machine_total = sum((line.cost for line in machine_lines), ZERO)
    labor_total = sum((line.cost for line in labor_lines), ZERO)
    batch_total = material_total + machine_total + labor_total

    divisor = Decimal(yield_qty)
    production_cost = batch_total / divisor
    packaging = sum((line.cost for line in packaging_lines), ZERO)
    total_cost = production_cost + packaging
    recommended = production_cost * settings.margin_multiplier + packaging

    has_custom = product.selling_price is not None and product.selling_price > 0
    selling_price = product.selling_price if has_custom else recommended
    profit = selling_price - total_cost
    margin_percent = profit / selling_price * 100 if selling_price > 0 else ZERO

    return ProductCosts(
        materials=material_lines,
        machines=tuple(machine_lines),
        labor=labor_lines,
        packaging=packaging_lines,
        yield_qty=yield_qty,
        material_total=material_total,
        machine_total=machine_total,
        labor_total=labor_total,
        batch_total=batch_total,
        material_per_unit=material_total / divisor,
        machine_per_unit=machine_total / divisor,
        labor_per_unit=labor_total / divisor,
        production_cost=production_cost,
        packaging_cost=packaging,
        total_cost=total_cost,
        recommended_price=recommended,
        selling_price=selling_price,
        has_custom_price=has_custom,
        profit=profit,
        margin_percent=margin_percent,
    )


def costs_to_view(costs: ProductCosts, shipping_cost=ZERO) -> dict:
    """Flaches Dict mit auf Cent gerundeten floats für Templates/JSON."""
    f = lambda v: float(money(v))
    return {
        "yield_qty": costs.yield_qty,
        # Chargenkosten
        "batch_material_cost": f(costs.material_total),
        "batch_machine_cost": f(costs.machine_total),
        "batch_labor_cost": f(costs.labor_total),
        "batch_total_cost": f(costs.batch_total),
        # pro Stück
        "material_cost": f(costs.material_per_unit),
        "machine_cost": f(costs.machine_per_unit),
        "labor_cost": f(costs.labor_per_unit),
        "production_cost": f(costs.production_cost),
        "packaging_cost": f(costs.packaging_cost),
        "shipping_cost": f(shipping_cost),
        "total_cost": f(costs.total_cost),
        "purchase_price": f(costs.total_cost),
        "recommended_selling_price": f(costs.recommended_price),
        "selling_price": f(costs.selling_price),
        "has_custom_selling_price": costs.has_custom_price,
        "profit": f(costs.profit),
        "margin_percent": float(costs.margin_percent.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)),
        # Zeilen für die Detailansicht
        "materials": [
            {"material_id": l.material_id, "name": l.name, "unit": l.unit, "amount": float(l.amount),
             "price_per_unit": float(l.price_per_unit), "cost": f(l.cost)}
            for l in costs.materials
        ],
        "machines": [
            {"machine_id": l.machine_id, "name": l.name, "billing_mode": l.billing_mode,
             "value": float(l.value), "rate": float(l.rate), "cost": f(l.cost)}
            for l in costs.machines
        ],
        "labor": [
            {"description": l.description, "minutes": float(l.minutes), "hourly_rate": float(l.hourly_rate),
             "cost": f(l.cost)}
            for l in costs.labor
        ],
        "labor_minutes": float(sum((l.minutes for l in costs.labor), ZERO)),
        "packaging": [
            {"material_id": l.material_id, "name": l.name, "unit": l.unit, "amount": float(l.amount),
             "price_per_unit": float(l.price_per_unit), "cost": f(l.cost)}
            for l in costs.packaging
        ],
    }
