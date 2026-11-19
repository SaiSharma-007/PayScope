from statistics import median

from payscope.seed_data import CURRENCIES, LOCATIONS, generate_employees


def test_seed_generates_a_repeatable_workforce_with_varied_pay():
    employees = list(generate_employees())

    assert employees == list(generate_employees())
    assert len({employee.code for employee in employees}) == 10_000
    assert len({employee.name for employee in employees}) > 5_000
    assert {employee.country for employee in employees} == LOCATIONS.keys()
    assert {employee.currency for employee in employees} == CURRENCIES.keys()

    us_employees = [employee for employee in employees if employee.country == "US"]
    engineer_pay = median(
        employee.annual_gross_base
        for employee in us_employees
        if employee.job_title == "Software Engineer"
    )
    manager_pay = median(
        employee.annual_gross_base
        for employee in us_employees
        if employee.job_title == "Engineering Manager"
    )
    assert manager_pay > engineer_pay
