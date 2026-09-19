"""Tests der reinen Kalkulation (kein Datenbankzugriff)."""
from decimal import Decimal

from calc import (
    BILLING_SHEET, BILLING_TIME, CalcSettings, LaborInput, MachineInput, MaterialInput, ProductInput,
    calculate_product, costs_to_view, dec, machine_cost, machine_cost_per_hour, machine_rate_breakdown,
    material_cost, money, recommended_sheet_price, sheet_cost_estimate,
)

D = Decimal
SETTINGS = CalcSettings(electricity_price_kwh=D("0.22"), margin_multiplier=D("2.0"))


def printer(minutes, power_w="100", depreciation="350", lifespan="3000"):
    return MachineInput(
        machine_id=1, name="Drucker", billing_mode=BILLING_TIME, value=D(minutes),
        depreciation_euro=D(depreciation), lifespan_hours=D(lifespan), power_w=D(power_w),
    )


def plotter(sheets, price="0.12"):
    return MachineInput(
        machine_id=2, name="Plotter", billing_mode=BILLING_SHEET, value=D(sheets), cost_per_sheet=D(price),
    )


def work(minutes, rate, description=""):
    return LaborInput(minutes=D(minutes), hourly_rate=D(rate), description=description)


def bag(price, amount=1, material_id=90):
    return MaterialInput(material_id=material_id, name="Beutel", unit="piece", amount=D(amount), price_per_unit=D(price))


def filament(grams, price="20", material_id=1, name="PLA"):
    return MaterialInput(material_id=material_id, name=name, unit="kg", amount=D(grams), price_per_unit=D(price))


class TestParsing:
    def test_dec_accepts_comma_and_none(self):
        assert dec("1,5") == D("1.5")
        assert dec(None) == 0
        assert dec("  ") == 0
        assert dec(2) == D(2)

    def test_money_rounds_half_up(self):
        assert money("0.125") == D("0.13")
        assert money("0.124") == D("0.12")


class TestSingleCosts:
    def test_material_in_grams_at_kg_price(self):
        assert material_cost(20, "11.90", "kg") == D("0.238")

    def test_cheap_material_keeps_full_precision(self):
        # Regression: früher wurde 0,0119 €/g als 0,01 gespeichert (Numeric(10,2)) -> 16 % zu billig
        assert material_cost(100, "11.90", "kg") == D("1.19")

    def test_material_per_sheet_and_piece(self):
        assert material_cost(3, "0.235", "sheet") == D("0.705")
        assert material_cost(4, "0.05", "piece") == D("0.20")

    def test_machine_hourly_rate(self):
        rate = machine_cost_per_hour(350, 3000, 100, "0.22")
        assert rate.quantize(D("0.0001")) == D("0.1387")

    def test_zero_lifespan_does_not_divide_by_zero(self):
        assert machine_cost_per_hour(350, 0, 0, "0.22") == D(350)

    def test_time_machine_cost(self):
        cost = machine_cost(printer(120), "0.22")
        assert cost.quantize(D("0.0001")) == D("0.2773")

    def test_sheet_machine_cost(self):
        assert machine_cost(plotter(5), "0.22") == D("0.60")


class TestProduct:
    def test_full_batch_example(self):
        product = ProductInput(
            yield_qty=4, labor=(work(10, 24),), packaging=(bag("0.10"),),
            materials=(filament(40),), machines=(printer(120),),
        )
        c = calculate_product(product, SETTINGS)

        assert money(c.material_total) == D("0.80")
        assert money(c.machine_total) == D("0.28")
        assert money(c.labor_total) == D("4.00")
        assert money(c.batch_total) == D("5.08")
        assert money(c.production_cost) == D("1.27")          # Charge / Ausbeute
        assert money(c.total_cost) == D("1.37")               # + Verpackung 1:1
        assert money(c.recommended_price) == D("2.64")        # Herstellkosten * 2 + Verpackung
        assert c.has_custom_price is False
        assert c.selling_price == c.recommended_price

    def test_yield_one_with_several_sheets_charges_the_whole_batch(self):
        # Regression: Formular rechnete Charge / 1, das gespeicherte Produkt teilte durch die Bogenzahl
        product = ProductInput(
            yield_qty=1,
            materials=(MaterialInput(1, "Sticker", "sheet", D(3), D("0.50")),),
        )
        c = calculate_product(product, SETTINGS)
        assert c.material_per_unit == D("1.50")
        assert c.production_cost == D("1.50")

    def test_yield_below_one_is_clamped(self):
        c = calculate_product(ProductInput(yield_qty=0, materials=(filament(50),)), SETTINGS)
        assert c.yield_qty == 1

    def test_multiple_materials_and_machines_are_summed(self):
        product = ProductInput(
            yield_qty=2,
            materials=(filament(20, "20", 1, "PLA weiß"), filament(10, "11.90", 2, "PLA rot")),
            machines=(printer(60), plotter(2, "0.10")),
        )
        c = calculate_product(product, SETTINGS)
        assert len(c.materials) == 2 and len(c.machines) == 2
        assert money(c.material_total) == D("0.52")     # 0,40 + 0,119
        assert money(c.machine_total) == D("0.34")      # 0,1387 + 0,20
        assert c.batch_total == c.material_total + c.machine_total

    def test_custom_selling_price_and_margin(self):
        product = ProductInput(
            yield_qty=1, labor=(work(60, 10),),
            selling_price=D("20"),
        )
        c = calculate_product(product, SETTINGS)
        assert c.has_custom_price is True
        assert c.selling_price == D(20)
        assert c.profit == D(10)
        assert c.margin_percent == D(50)

    def test_zero_selling_price_falls_back_to_recommendation(self):
        product = ProductInput(selling_price=D(0), labor=(work(30, 20),))
        c = calculate_product(product, SETTINGS)
        assert c.has_custom_price is False
        assert c.selling_price == c.recommended_price == D(20)

    def test_empty_product_costs_only_packaging(self):
        c = calculate_product(ProductInput(packaging=(bag("0.30"),)), SETTINGS)
        assert c.production_cost == 0
        assert c.total_cost == D("0.30")
        assert c.recommended_price == D("0.30")
        assert c.profit == 0 and c.margin_percent == 0

    def test_margin_multiplier_applies_only_to_production_cost(self):
        settings = CalcSettings(electricity_price_kwh=D("0.22"), margin_multiplier=D("3"))
        product = ProductInput(labor=(work(60, 10),), packaging=(bag(1),))
        c = calculate_product(product, settings)
        assert c.recommended_price == D(31)  # 10 * 3 + 1

    def test_electricity_price_changes_time_machines_only(self):
        cheap = CalcSettings(electricity_price_kwh=D("0.10"))
        dear = CalcSettings(electricity_price_kwh=D("0.50"))
        product = ProductInput(machines=(printer(60, power_w="1000"), plotter(1)))
        low = calculate_product(product, cheap).machine_total
        high = calculate_product(product, dear).machine_total
        assert high - low == D("0.40")  # nur 1 kW * 1 h * 0,40 €/kWh Unterschied


class TestMachineRateHelpers:
    def test_breakdown_sums_to_the_hourly_rate(self):
        total, strom, abschreibung = machine_rate_breakdown(350, 3000, 100, "0.22")
        assert total == strom + abschreibung == machine_cost_per_hour(350, 3000, 100, "0.22")
        assert strom == D("0.022")
        assert abschreibung.quantize(D("0.0001")) == D("0.1167")

    def test_sheet_cost_estimate(self):
        machine, total = sheet_cost_estimate(D("0.1387"), D("2.5"), D("0.07"))
        assert machine.quantize(D("0.0001")) == D("0.0058")
        assert total.quantize(D("0.0001")) == D("0.0758")

    def test_recommended_sheet_price_rounds_up_to_cents_with_a_floor(self):
        assert recommended_sheet_price(D("0.0758")) == D("0.08")   # Untergrenze
        assert recommended_sheet_price(D("0.0801")) == D("0.09")   # aufgerundet
        assert recommended_sheet_price(D("0.12")) == D("0.12")


class TestLaborAndPackaging:
    def test_labor_steps_have_their_own_rates(self):
        product = ProductInput(labor=(work(30, 20, "Entgraten"), work(15, 40, "Montage")))
        c = calculate_product(product, SETTINGS)
        assert [l.cost for l in c.labor] == [D(10), D(10)]
        assert c.labor_total == D(20)
        assert [l.description for l in c.labor] == ["Entgraten", "Montage"]

    def test_labor_is_per_batch_and_divided_by_yield(self):
        c = calculate_product(ProductInput(yield_qty=4, labor=(work(60, 20),)), SETTINGS)
        assert c.labor_total == D(20) and c.labor_per_unit == D(5)

    def test_packaging_is_per_piece_and_not_divided_by_yield(self):
        product = ProductInput(yield_qty=10, packaging=(bag("0.05", amount=2), bag("0.20", material_id=91)))
        c = calculate_product(product, SETTINGS)
        assert c.packaging_cost == D("0.30")         # 2 x 0,05 + 1 x 0,20, egal bei welcher Ausbeute
        assert c.total_cost == D("0.30")
        assert len(c.packaging) == 2

    def test_packaging_gets_no_margin(self):
        product = ProductInput(labor=(work(60, 10),), packaging=(bag("1"),))
        c = calculate_product(product, CalcSettings(margin_multiplier=D(3)))
        assert c.recommended_price == D(31)          # 10 x 3 + 1

    def test_packaging_in_grams_uses_the_unit_factor(self):
        wrap = MaterialInput(material_id=5, name="Folie", unit="kg", amount=D(20), price_per_unit=D(10))
        c = calculate_product(ProductInput(packaging=(wrap,)), SETTINGS)
        assert c.packaging_cost == D("0.2")          # 20 g bei 10 €/kg


class TestView:
    def test_view_is_rounded_floats_with_lines(self):
        product = ProductInput(
            yield_qty=4, labor=(work(10, 24),), packaging=(bag("0.10"),),
            materials=(filament(40),), machines=(printer(120),),
        )
        view = costs_to_view(calculate_product(product, SETTINGS), shipping_cost=D("1.5"))
        assert view["production_cost"] == 1.27
        assert view["purchase_price"] == view["total_cost"] == 1.37
        assert view["recommended_selling_price"] == 2.64
        assert view["shipping_cost"] == 1.5
        assert view["materials"][0]["name"] == "PLA"
        assert view["machines"][0]["billing_mode"] == BILLING_TIME
        assert view["labor"][0]["cost"] == 4.0 and view["labor_minutes"] == 10.0
        assert view["packaging"][0]["name"] == "Beutel" and view["packaging"][0]["cost"] == 0.1
