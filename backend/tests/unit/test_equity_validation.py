from datetime import date

import pytest
from payscope.compensation.equity_schemas import AwardDraft
from pydantic import ValidationError

BASE = {
    "kind": "rsu",
    "units": "10.25",
    "grant_date": "2020-01-01",
    "grant_currency": "USD",
    "package_currency": "INR",
}
ALLOCATION = {"year": 2020, "currency_code": "INR", "amount": "0.00"}


@pytest.mark.parametrize(
    "change",
    [
        {"units": "0"},
        {"units": "NaN"},
        {"units": "0.00001"},
        {"units": 10},
        {"kind": "option"},
        {"exercise_price": "0"},
        {"valuation": "1"},
        {"valuation_date": "2020-02-01", "valuation": "10.001"},
        {"grant_date": date.max.isoformat()},
        {"last_year": 2019},
        {"vesting": [{"date": "2021-01-01", "units": "11"}]},
        {"vesting": [{"date": "2019-12-31", "units": "1"}]},
        {"allocations": [ALLOCATION, ALLOCATION]},
        {"allocations": [ALLOCATION | {"year": 2019}]},
        {"allocations": [ALLOCATION | {"amount": "0.001"}]},
        {"allocations": [ALLOCATION | {"currency_code": "JPY"}]},
    ],
)
def test_invalid_awards(change):
    with pytest.raises(ValidationError):
        AwardDraft.model_validate(BASE | change)


def test_zero_allocation_and_partial_vesting_are_explicit():
    award = AwardDraft.model_validate(
        BASE
        | {
            "kind": "option",
            "exercise_price": "4.1250",
            "allocations": [ALLOCATION],
            "vesting": [{"date": "2021-01-01", "units": "4.25"}],
        }
    )
    assert award.allocations[0].amount == 0
    assert award.units - award.vesting[0].units == 6
    assert award.valuation is None


def test_cross_field_errors_point_to_the_missing_date_and_affected_rows():
    with pytest.raises(ValidationError) as failure:
        AwardDraft.model_validate(
            BASE
            | {
                "valuation": "2000",
                "vesting": [{"date": "2021-01-01", "units": "11"}],
                "allocations": [ALLOCATION, ALLOCATION],
            }
        )
    assert [error["loc"] for error in failure.value.errors()] == [
        ("valuation_date",),
        ("vesting", 0, "units"),
        ("allocations", 1, "year"),
    ]
