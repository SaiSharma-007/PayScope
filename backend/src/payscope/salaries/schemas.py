import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_serializer, field_validator

_ANNUAL_AMOUNT = re.compile(r"[0-9]{1,9}(?:\.[0-9]{1,2})?")


class SalaryUpdate(BaseModel):
    annual_gross_base: Decimal
    currency_code: Literal["INR", "USD", "GBP", "EUR"]

    @field_validator("annual_gross_base", mode="before", json_schema_input_type=str)
    @classmethod
    def validate_amount(cls, value: object) -> Decimal:
        if not isinstance(value, str) or _ANNUAL_AMOUNT.fullmatch(value) is None:
            raise ValueError(
                "Enter a decimal string with at most nine whole and two fractional digits."
            )
        amount = Decimal(value)
        if amount <= 0:
            raise ValueError("Annual gross base salary must be at least 0.01.")
        return amount


class SalaryResponse(BaseModel):
    annual_gross_base: Decimal
    currency_code: str
    updated_at: datetime

    @field_serializer("annual_gross_base")
    def serialize_amount(self, amount: Decimal) -> str:
        return format(amount, ".2f")
