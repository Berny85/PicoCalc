"""Material-Einheiten an einer einzigen Stelle.

Der Preis eines Materials bezieht sich auf die Einheit (z.B. 11,90 €/kg), die Menge im Produkt
wird aber in der Eingabe-Einheit erfasst (z.B. 20 g). ``factor`` rechnet die Eingabe-Einheit in
die Preis-Einheit um: Kosten = Menge / factor * Preis.
"""
from decimal import Decimal

MATERIAL_UNITS = {
    "kg": {
        "label": "Kilogramm (kg)",
        "price_label": "€/kg",
        "input_label": "Gramm",
        "factor": Decimal(1000),
    },
    "sheet": {
        "label": "Bogen",
        "price_label": "€/Bogen",
        "input_label": "Bogen",
        "factor": Decimal(1),
    },
    "piece": {
        "label": "Stück",
        "price_label": "€/Stück",
        "input_label": "Stück",
        "factor": Decimal(1),
    },
    "pack": {
        "label": "Packung",
        "price_label": "€/Packung",
        "input_label": "Packung",
        "factor": Decimal(1),
    },
    "m": {
        "label": "Meter (m)",
        "price_label": "€/m",
        "input_label": "Meter",
        "factor": Decimal(1),
    },
    "m2": {
        "label": "Quadratmeter (m²)",
        "price_label": "€/m²",
        "input_label": "m²",
        "factor": Decimal(1),
    },
}

DEFAULT_UNIT = "piece"


def is_valid_unit(unit: str) -> bool:
    return unit in MATERIAL_UNITS


def unit_factor(unit: str) -> Decimal:
    return MATERIAL_UNITS[unit]["factor"]


def input_label(unit: str) -> str:
    return MATERIAL_UNITS[unit]["input_label"] if unit in MATERIAL_UNITS else unit


def price_label(unit: str) -> str:
    return MATERIAL_UNITS[unit]["price_label"] if unit in MATERIAL_UNITS else f"€/{unit}"


def units_for_json() -> list[dict]:
    """Einheiten für Formulare/JS (Faktor als float, da nur zur Anzeige der Live-Vorschau)."""
    return [
        {"key": key, "label": u["label"], "input_label": u["input_label"],
         "price_label": u["price_label"], "factor": float(u["factor"])}
        for key, u in MATERIAL_UNITS.items()
    ]
