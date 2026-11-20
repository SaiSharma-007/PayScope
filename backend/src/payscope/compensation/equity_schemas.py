from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, ValidationError, model_validator

from payscope.compensation.schemas import MAX_AMOUNT, Currency, DecimalInput, Input

Year = Annotated[int, Field(ge=1900, le=9998)]


def validate_money(value: Decimal) -> Decimal:
    if value > MAX_AMOUNT or value.as_tuple().exponent < -2:
        raise ValueError(
            "Use at most two decimal places and an amount up to 999999999.99."
        )
    return value


EquityMoney = Annotated[DecimalInput, AfterValidator(validate_money)]


class Vest(Input):
    date: date
    units: DecimalInput = Field(gt=0)


class Allocation(Input):
    year: Year
    amount: EquityMoney
    currency_code: Currency


class AwardDraft(Input):
    kind: Literal["rsu", "option"]
    units: DecimalInput = Field(gt=0)
    grant_date: date
    grant_currency: Currency
    package_currency: Currency
    exercise_price: DecimalInput | None = None
    valuation: EquityMoney | None = None
    valuation_date: date | None = None
    last_year: Year | None = None
    vesting: list[Vest] = Field(default_factory=list, max_length=120)
    allocations: list[Allocation] = Field(default_factory=list, max_length=60)
    expected_version: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_award(self):
        errors = []

        def invalid(*location, message):
            errors.append(
                {
                    "type": "value_error",
                    "loc": location,
                    "ctx": {"error": ValueError(message)},
                }
            )

        if not 1900 <= self.grant_date.year <= 9998 or self.grant_date > date.today():
            invalid("grant_date", message="Enter a grant date between 1900 and today.")
        if (self.kind == "option") != (self.exercise_price is not None):
            invalid(
                "exercise_price" if self.kind == "option" else "kind",
                message="Options require an exercise price. Leave it blank for RSUs.",
            )
        if self.valuation is not None and self.valuation_date is None:
            invalid("valuation_date", message="Enter the date of this valuation.")
        if self.valuation is None and self.valuation_date is not None:
            invalid("valuation", message="Enter the grant valuation for this date.")
        if (
            self.valuation_date
            and not self.grant_date <= self.valuation_date <= date.today()
        ):
            invalid(
                "valuation_date", message="Use a date between the grant date and today."
            )
        if self.last_year is not None and self.last_year < self.grant_date.year:
            invalid("last_year", message="Use the grant year or a later year.")
        dates = set()
        scheduled = Decimal(0)
        for index, row in enumerate(self.vesting):
            if row.date < self.grant_date:
                invalid(
                    "vesting",
                    index,
                    "date",
                    message="Use the grant date or a later date.",
                )
            elif row.date in dates:
                invalid(
                    "vesting",
                    index,
                    "date",
                    message="This vesting date is already listed.",
                )
            dates.add(row.date)
            scheduled += row.units
            if scheduled > self.units:
                invalid(
                    "vesting",
                    index,
                    "units",
                    message="Scheduled units exceed the award units.",
                )
        years = set()
        for index, row in enumerate(self.allocations):
            if not self.grant_date.year <= row.year <= (self.last_year or 9998):
                invalid(
                    "allocations",
                    index,
                    "year",
                    message="Use a year within the award’s allocation period.",
                )
            elif row.year in years:
                invalid(
                    "allocations",
                    index,
                    "year",
                    message="This allocation year is already listed.",
                )
            years.add(row.year)
        if errors:
            raise ValidationError.from_exception_data(type(self).__name__, errors)
        return self
