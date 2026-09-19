"""Gemeinsame Jinja-Umgebung (Templates und Filter)."""
from fastapi.templating import Jinja2Templates

from calc import dec

templates = Jinja2Templates(directory="templates")


def format_price(value) -> str:
    """Preis mit mindestens 2 und höchstens 4 Nachkommastellen, deutsches Komma (11,90 / 0,2355)"""
    text = f"{dec(value):.4f}".rstrip("0")
    integer, _, fraction = text.partition(".")
    return f"{integer},{fraction.ljust(2, '0')}"


templates.env.filters["price"] = format_price
