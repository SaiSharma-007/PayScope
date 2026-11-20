from decimal import ROUND_HALF_UP, Decimal

from payscope.compensation.schemas import (
    MAX_AMOUNT,
    CalculatedComponent,
    Calculation,
    Component,
    PackageDraft,
    decimal_text,
)


def calculate(draft: PackageDraft, components: list[Component]) -> Calculation:
    overrides = {override.code: override for override in draft.overrides}
    if overrides.keys() - {component.code for component in components}:
        raise ValueError(
            "An override refers to a component that is not in this package."
        )
    lines = []
    earnings = draft.annual_basic_pay
    employer_costs = deductions = target_extra = Decimal("0.00")
    guaranteed_cost = draft.annual_basic_pay
    for component in components:
        raw = (
            component.value
            if component.method == "fixed"
            else draft.annual_basic_pay * component.value / 100
        )
        calculated = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        override = overrides.get(component.code)
        amount = override.amount if override else calculated
        if calculated > MAX_AMOUNT or amount > MAX_AMOUNT:
            raise ValueError(f"{component.label} exceeds the supported amount limit.")
        if component.commitment == "guaranteed":
            if component.category == "earning":
                earnings += amount
            elif component.category == "employer_cost":
                employer_costs += amount
            else:
                deductions += amount
            if component.included_in_cost:
                guaranteed_cost += amount
        elif component.included_in_cost:
            target_extra += amount
        lines.append(
            CalculatedComponent(
                **component.model_dump(),
                calculated_amount=calculated,
                amount=amount,
                override_reason=override.reason if override else None,
                explanation="Fixed annual amount"
                if component.method == "fixed"
                else f"{decimal_text(component.value)}% of annual basic pay",
            )
        )
    target_cost = guaranteed_cost + target_extra
    if (
        max(earnings, employer_costs, deductions, guaranteed_cost, target_cost)
        > MAX_AMOUNT
    ):
        raise ValueError(
            "The package total exceeds 999999999.99. Reduce its component amounts."
        )
    return Calculation(
        annual_basic_pay=draft.annual_basic_pay,
        currency_code=draft.currency_code,
        components=lines,
        guaranteed_earnings=earnings,
        guaranteed_employer_costs=employer_costs,
        employee_deductions=deductions,
        guaranteed_cost=guaranteed_cost,
        target_cost=target_cost,
    )
