from decimal import Decimal

import pytest
from pydantic import ValidationError

from payscope.salaries.schemas import SalaryUpdate


@pytest.mark.parametrize("amount", ["0.01", "999999999.99", "42", "42.1"])
def test_salary_accepts_decimal_strings(amount):
    salary = SalaryUpdate(annual_gross_base=amount, currency_code="INR")
    assert salary.annual_gross_base == Decimal(amount)


@pytest.mark.parametrize(
    "amount",
    ["0", "-1", "1000000000", "0.001", "1.000", "NaN", "Infinity", "1e2", "1,000", 42, None],
)
def test_salary_rejects_invalid_amounts(amount):
    with pytest.raises(ValidationError) as error:
        SalaryUpdate(annual_gross_base=amount, currency_code="INR")
    assert error.value.errors()[0]["loc"] == ("annual_gross_base",)


def test_salary_rejects_unsupported_currency():
    with pytest.raises(ValidationError) as error:
        SalaryUpdate(annual_gross_base="42", currency_code="JPY")
    assert error.value.errors()[0]["loc"] == ("currency_code",)
