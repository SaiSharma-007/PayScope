from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from random import Random

from faker import Faker

EMPLOYEE_COUNT = 10_000

CURRENCIES = {
    "INR": "Indian Rupee",
    "USD": "US Dollar",
    "GBP": "British Pound",
    "EUR": "Euro",
}

DEPARTMENTS = {
    "Engineering": {"Software Engineer": 115, "Quality Engineer": 95, "Engineering Manager": 150},
    "Finance": {"Financial Analyst": 100, "Accountant": 90, "Finance Manager": 135},
    "Operations": {"Operations Analyst": 85, "Program Manager": 105, "Operations Manager": 125},
    "People": {"HR Specialist": 85, "Recruiter": 95, "HR Manager": 120},
    "Sales": {"Account Executive": 105, "Sales Analyst": 95, "Sales Manager": 135},
}


@dataclass(frozen=True, slots=True)
class Location:
    country: str
    currency: str
    locale: str
    annual_range: tuple[int, int]


LOCATIONS = {
    "IN": Location("India", "INR", "en_IN", (450_000, 2_400_000)),
    "US": Location("United States", "USD", "en_US", (48_000, 145_000)),
    "GB": Location("United Kingdom", "GBP", "en_GB", (28_000, 98_000)),
    "DE": Location("Germany", "EUR", "de_DE", (39_000, 105_000)),
    "FR": Location("France", "EUR", "fr_FR", (35_000, 91_000)),
}


@dataclass(frozen=True, slots=True)
class DemoEmployee:
    code: str
    name: str
    country: str
    department: str
    job_title: str
    currency: str
    annual_gross_base: Decimal


def generate_employees() -> Iterator[DemoEmployee]:
    random = Random(42)
    names = {code: Faker(location.locale) for code, location in LOCATIONS.items()}
    for seed, faker in enumerate(names.values(), start=42):
        faker.seed_instance(seed)

    country_codes = tuple(LOCATIONS)
    department_names = tuple(DEPARTMENTS)
    for number in range(1, EMPLOYEE_COUNT + 1):
        country = random.choice(country_codes)
        location = LOCATIONS[country]
        department = random.choice(department_names)
        roles = DEPARTMENTS[department]
        job_title = random.choices(tuple(roles), weights=(55, 35, 10), k=1)[0]
        faker = names[country]
        base_amount = random.triangular(*location.annual_range)
        salary = round(base_amount * roles[job_title] / 100, -2)
        yield DemoEmployee(
            code=f"EMP-{number:06d}",
            name=f"{faker.first_name()} {faker.last_name()}",
            country=country,
            department=department,
            job_title=job_title,
            currency=location.currency,
            annual_gross_base=Decimal(int(salary)),
        )
