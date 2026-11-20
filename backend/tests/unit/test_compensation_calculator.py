from decimal import Decimal

import pytest
from payscope.compensation.calculator import calculate
from payscope.compensation.schemas import Component, PackageDraft, RuleDraft
from pydantic import ValidationError


def component(**changes):
    return Component.model_validate(
        dict(
            code="yearly_bonus",
            label="Yearly bonus",
            method="percent_of_base",
            value="1",
        )
        | changes
    )


def draft(**changes):
    return PackageDraft.model_validate(
        dict(
            annual_basic_pay="1000000.00",
            currency_code="INR",
            effective_date="2026-01-01",
        )
        | changes
    )


def test_custom_bonus_and_explained_decimal_values():
    result = calculate(draft(), [component()])
    assert result.components[0].amount == Decimal("10000.00")
    assert result.guaranteed_cost == result.target_cost == Decimal("1010000.00")
    assert result.model_dump(mode="json")["guaranteed_cost"] == "1010000.00"
    assert result.components[0].explanation == "1% of annual basic pay"


def test_rounding_and_totals_use_visible_lines():
    result = calculate(draft(annual_basic_pay="0.50"), [component()])
    assert result.components[0].amount == Decimal("0.01")
    assert result.guaranteed_cost == Decimal("0.51")


def test_guaranteed_target_and_employee_deductions_stay_separate():
    components = [
        component(),
        component(code="target", commitment="target"),
        component(code="employee_pf", category="deduction", included_in_cost=False),
        component(code="benefit", category="employer_cost"),
    ]
    result = calculate(draft(), components)
    assert result.guaranteed_earnings == Decimal("1010000")
    assert (
        result.guaranteed_employer_costs
        == result.employee_deductions
        == Decimal("10000")
    )
    assert result.guaranteed_cost == Decimal("1020000")
    assert result.target_cost == Decimal("1030000")


def test_override_preserves_formula_amount_and_reason():
    result = calculate(
        draft(
            overrides=[
                {
                    "code": "yearly_bonus",
                    "amount": "0.00",
                    "reason": "Individual agreement",
                }
            ]
        ),
        [component()],
    )
    assert result.components[0].calculated_amount == Decimal("10000")
    assert result.components[0].amount == 0
    assert result.components[0].override_reason == "Individual agreement"
    assert result.guaranteed_cost == Decimal("1000000")


def test_manual_empty_package_and_zero_fixed_component():
    assert calculate(draft(), []).guaranteed_cost == Decimal("1000000")
    zero = Component(code="optional", label="Optional", value="0")
    assert calculate(draft(), [zero]).components[0].amount == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"annual_basic_pay": 100},
        {"annual_basic_pay": "NaN"},
        {"annual_basic_pay": "-1"},
        {"annual_basic_pay": "0"},
        {"annual_basic_pay": "100.001"},
        {"currency_code": "JPY"},
        {"effective_date": "9999-01-01"},
        {"rule_version_id": "not-a-uuid"},
        {"guaranteed_cost": "1"},
        {"overrides": [{"code": "yearly_bonus", "amount": "1", "reason": " "}]},
        {
            "overrides": [
                {"code": "yearly_bonus", "amount": "1.001", "reason": "Agreement"}
            ]
        },
    ],
)
def test_invalid_package_inputs(changes):
    with pytest.raises(ValidationError):
        draft(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"code": "basic_pay"},
        {"code": "x = eval()"},
        {"value": "Infinity"},
        {"value": "10000.0001"},
        {"method": "expression"},
        {"basis": "other_component"},
        {"category": "deduction"},
        {"method": "fixed", "value": "1.001"},
    ],
)
def test_invalid_component_definitions(changes):
    with pytest.raises(ValidationError):
        Component.model_validate(
            dict(code="bonus", label="Bonus", method="percent_of_base", value="1")
            | changes
        )


def test_duplicate_codes_and_component_limit():
    rule = dict(
        name="India",
        country_code="IN",
        currency_code="INR",
        components=[component().model_dump(mode="json")] * 2,
    )
    with pytest.raises(ValidationError):
        RuleDraft.model_validate(rule)
    with pytest.raises(ValidationError):
        RuleDraft.model_validate(
            rule
            | {
                "components": [
                    {"code": f"c{i}", "label": "Benefit", "value": "0"}
                    for i in range(33)
                ]
            }
        )


def test_unknown_override_and_overflow():
    with pytest.raises(ValueError, match="not in this package"):
        calculate(
            draft(
                overrides=[{"code": "unknown", "amount": "1", "reason": "Agreement"}]
            ),
            [],
        )
    with pytest.raises(ValueError, match="total exceeds"):
        calculate(draft(annual_basic_pay="999999999.99"), [component()])
    with pytest.raises(ValueError, match="amount limit"):
        calculate(
            draft(annual_basic_pay="999999999.99"),
            [
                Component(
                    code="bonus", label="Bonus", method="percent_of_base", value="200"
                )
            ],
        )
