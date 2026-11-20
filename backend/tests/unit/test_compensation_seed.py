from datetime import date
from decimal import Decimal

import pytest

from payscope.compensation.seed import PROFILES, demo_package, demo_rule
from payscope.seed_data import generate_employees


@pytest.mark.parametrize("country", PROFILES)
@pytest.mark.parametrize(
    "amount", ["0.01", "0.02", "10000.01", "900000.00", "999999999.99"]
)
def test_country_package_preserves_original_total(country, amount):
    total = Decimal(amount)
    result = demo_package(country, total, date(2026, 1, 1))
    assert result.guaranteed_cost == result.target_cost == total
    assert result.annual_basic_pay > 0
    assert len(result.components) == 5
    assert result.employee_deductions >= 0
    assert result.components[-1].override_reason
    assert demo_rule(country).country_code == country


def test_every_seeded_total_reconciles_and_generation_is_deterministic():
    totals = {}
    count = 0
    for employee in generate_employees():
        package = demo_package(
            employee.country, employee.annual_gross_base, date(2026, 1, 1)
        )
        assert package.guaranteed_cost == employee.annual_gross_base
        totals[employee.country] = (
            totals.get(employee.country, Decimal(0)) + package.guaranteed_cost
        )
        count += 1
    assert count == 10000
    assert set(totals) == set(PROFILES)


@pytest.mark.parametrize("total", [Decimal("10000.00"), Decimal("999999999.99")])
def test_target_demo_bonus_preserves_guaranteed_total(total):
    package = demo_package("IN", total, date(2022, 1, 1), with_target=True)
    assert package.guaranteed_cost == total
    assert package.target_cost == min(total * Decimal("1.03"), Decimal("999999999.99"))
