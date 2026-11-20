import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

MAX_AMOUNT = Decimal("999999999.99")
MAX_COMPONENTS = 32


def decimal_string(value: object) -> Decimal:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,4})?", value) is None
    ):
        raise ValueError(
            "Enter a non-negative decimal string with up to four fractional digits."
        )
    return Decimal(value)


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


DecimalInput = Annotated[
    Decimal,
    BeforeValidator(decimal_string),
    PlainSerializer(decimal_text, return_type=str, when_used="json"),
]
Money = Annotated[
    Decimal,
    PlainSerializer(
        lambda value: format(value, ".2f"), return_type=str, when_used="json"
    ),
]
Currency = Literal["INR", "USD", "GBP", "EUR"]
Category = Literal["earning", "employer_cost", "deduction"]
Commitment = Literal["guaranteed", "target"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Component(Input):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,49}$")
    label: str = Field(min_length=1, max_length=80)
    category: Category = "earning"
    method: Literal["fixed", "percent_of_base"] = "fixed"
    value: DecimalInput
    commitment: Commitment = "guaranteed"
    included_in_cost: bool = True

    @model_validator(mode="after")
    def valid_component(self):
        if self.code == "basic_pay":
            raise ValueError(
                "Basic pay is already included. Choose another component code."
            )
        if self.method == "fixed" and (
            self.value > MAX_AMOUNT or self.value.as_tuple().exponent < -2
        ):
            raise ValueError(
                "Fixed amounts need at most two decimal places and cannot exceed 999999999.99."
            )
        if self.method == "percent_of_base" and self.value > Decimal("10000"):
            raise ValueError("A percentage cannot exceed 10000% of basic pay.")
        if self.category == "deduction" and (
            self.included_in_cost or self.commitment != "guaranteed"
        ):
            raise ValueError(
                "Employee deductions must be guaranteed and excluded from company cost."
            )
        return self


def unique_components(components):
    codes = [component.code for component in components]
    if len(codes) != len(set(codes)):
        raise ValueError("Component codes must be unique.")


class RuleDraft(Input):
    name: str = Field(min_length=1, max_length=100)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    currency_code: Currency
    components: list[Component] = Field(default_factory=list, max_length=MAX_COMPONENTS)

    @model_validator(mode="after")
    def unique_codes(self):
        unique_components(self.components)
        return self


class RulePublish(RuleDraft):
    expected_version: int = Field(ge=1)


class RuleStatus(Input):
    active: bool
    expected_version: int = Field(ge=1)


class Override(Input):
    code: str
    amount: DecimalInput
    reason: str = Field(min_length=3, max_length=300)

    @field_validator("amount")
    @classmethod
    def valid_amount(cls, amount):
        if amount > MAX_AMOUNT or amount.as_tuple().exponent < -2:
            raise ValueError(
                "Overrides need at most two decimal places and cannot exceed 999999999.99."
            )
        return amount


class PackageDraft(Input):
    annual_basic_pay: DecimalInput
    currency_code: Currency
    effective_date: date
    rule_version_id: UUID | None = None
    components: list[Component] = Field(default_factory=list, max_length=MAX_COMPONENTS)
    overrides: list[Override] = Field(default_factory=list, max_length=MAX_COMPONENTS)

    @field_validator("annual_basic_pay")
    @classmethod
    def valid_basic_pay(cls, amount):
        if (
            not Decimal("0.01") <= amount <= MAX_AMOUNT
            or amount.as_tuple().exponent < -2
        ):
            raise ValueError(
                "Annual basic pay must be 0.01–999999999.99 with at most two decimal places."
            )
        return amount

    @field_validator("effective_date")
    @classmethod
    def valid_effective_date(cls, effective_date):
        if effective_date > date.today():
            raise ValueError(
                "Use today or an earlier effective date. Scheduled changes are not supported."
            )
        return effective_date

    @model_validator(mode="after")
    def valid_package(self):
        if self.rule_version_id and self.components:
            raise ValueError(
                "A rule supplies its own components. Use overrides to change employee amounts."
            )
        unique_components(self.components)
        codes = [override.code for override in self.overrides]
        if len(codes) != len(set(codes)):
            raise ValueError("Each component can have only one override.")
        return self


class PackageSave(PackageDraft):
    expected_version: int = Field(ge=0)


class CalculatedComponent(BaseModel):
    code: str
    label: str
    category: Category
    method: Literal["fixed", "percent_of_base"]
    value: Annotated[
        Decimal, PlainSerializer(decimal_text, return_type=str, when_used="json")
    ]
    commitment: Commitment
    included_in_cost: bool
    calculated_amount: Money
    amount: Money
    override_reason: str | None = None
    explanation: str


class Calculation(BaseModel):
    annual_basic_pay: Money
    currency_code: Currency
    components: list[CalculatedComponent]
    guaranteed_earnings: Money
    guaranteed_employer_costs: Money
    employee_deductions: Money
    guaranteed_cost: Money
    target_cost: Money
    equity_status: Literal["not_configured"] = "not_configured"


class RuleVersion(BaseModel):
    id: UUID
    rule_id: UUID
    number: int
    name: str
    country_code: str
    currency_code: Currency
    components: list[Component]
    created_at: datetime


class RuleSummary(BaseModel):
    id: UUID
    name: str
    country_code: str
    currency_code: Currency
    active: bool
    latest_version: int
    version_id: UUID


class PackageResponse(Calculation):
    employee_id: int
    version: int
    effective_date: date
    rule_version_id: UUID | None
    rule_name: str | None
    rule_number: int | None
    updated_by: UUID
    updated_at: datetime
