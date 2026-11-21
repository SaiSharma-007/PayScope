from collections.abc import Iterable
from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from payscope.analytics.schemas import ReportFilters, SalaryReport, SalaryStatistics, HeadcountStatistics
from payscope.employees.service import get_reference_data

MAX_GROUPS = 50
Metric = Literal["minimum", "median", "maximum", "average", "headcount"]
Statement = Literal["value", "highest", "lowest", "tied highest", "tied lowest"]
MetricFields = {
    "minimum": "minimum",
    "median": "median",
    "maximum": "maximum",
    "average": "mean",
    "headcount": "headcount",
}
MetricLabels = {
    "minimum": "minimum base pay",
    "median": "median base pay",
    "maximum": "maximum base pay",
    "average": "average base pay",
    "headcount": "employees with a recorded salary",
}


class InvalidToolRequest(ValueError):
    pass


class OptionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: Annotated[str, Field(max_length=120)] | None = None


class SummaryRequest(ReportFilters):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["summary", "highest", "lowest"] = "summary"
    metric: Metric | None = None

    @model_validator(mode="after")
    def validate_ranking(self) -> SummaryRequest:
        if self.operation != "summary" and (
            self.group_by is None or self.metric not in ("median", "average", "headcount")
        ):
            raise ValueError(
                "A ranking requires a grouping and an average, median, or headcount metric."
            )
        if self.metric == "headcount" and self.currency_code is not None:
            raise ValueError("Workforce headcount is independent of currency; omit currency_code.")
        return self


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: Annotated[str, Field(min_length=1, max_length=64)]
    evidence_id: str
    group: str
    currency: str
    metric: Metric
    statement: Statement


class WriterAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[Claim]


@dataclass(frozen=True)
class EvidenceRow:
    statistics: SalaryStatistics | HeadcountStatistics
    id: UUID

    @property
    def group(self) -> str:
        return (
            str(self.statistics.group_id)
            if self.statistics.group_id is not None
            else "all"
        )

    def as_payload(self) -> dict:
        return self.statistics.model_dump(mode="json") | {
            "evidence_id": str(self.id),
            "group": self.group,
        }


@dataclass(frozen=True)
class Evidence:
    request: SummaryRequest
    revision: int
    currency_code: str | None
    rows: tuple[EvidenceRow, ...]

    def winners(self) -> tuple[EvidenceRow, ...]:
        if self.request.operation == "summary" or not self.rows:
            return ()
        field = MetricFields[self.request.metric]
        scores = [getattr(row.statistics, field) for row in self.rows]
        winning_value = (max if self.request.operation == "highest" else min)(scores)
        return tuple(
            row
            for row, score in zip(self.rows, scores, strict=True)
            if score == winning_value
        )

    def card(self) -> dict:
        return {
            "revision": self.revision,
            "currency_code": self.currency_code,
            "report_type": "workforce_headcount" if self.request.metric == "headcount" else "annual_gross_base",
            "filters": self.request.model_dump(
                exclude={"operation", "metric"},
                exclude_none=True,
            )
            | ({"currency_code": self.currency_code} if self.currency_code else {}),
            "operation": self.request.operation,
            "metric": self.request.metric,
            "ranking_evidence_ids": [str(row.id) for row in self.winners()],
            "rows": [row.as_payload() for row in self.rows],
        }


async def report_options(database: AsyncSession, request: OptionsRequest) -> dict:
    references = (await get_reference_data(database)).model_dump()
    query = (request.query or "").strip().casefold()
    options = {}
    for key, candidates in references.items():
        matches = [
            candidate
            for candidate in candidates
            if not query
            or query in candidate["name"].casefold()
            or query == candidate.get("code", "").casefold()
        ]
        options[key] = matches[:100]
        if len(matches) > 100:
            options.setdefault("truncated", []).append(key)
    return options


async def validate_report_filters(
    database: AsyncSession, request: SummaryRequest
) -> None:
    references = await get_reference_data(database)
    supported = {
        "country_code": {option.code for option in references.countries},
        "department_id": {option.id for option in references.departments},
        "job_title_id": {option.id for option in references.job_titles},
        "currency_code": {option.code for option in references.currencies},
    }
    for field, values in supported.items():
        value = getattr(request, field)
        if value is not None and value not in values:
            raise InvalidToolRequest(
                f"Unknown {field}. Resolve it with get_report_options."
            )


def currencies_in(report: SalaryReport) -> list[str]:
    return sorted({result.currency_code for result in report.rows if result.currency_code})


def make_evidence(request: SummaryRequest, report: SalaryReport) -> Evidence:
    codes = currencies_in(report)
    if len(codes) > 1 or len(report.rows) > MAX_GROUPS:
        raise ValueError("Report evidence exceeds the supported scope.")
    return Evidence(
        request,
        report.revision,
        codes[0] if codes else request.currency_code,
        tuple(EvidenceRow(row, uuid4()) for row in report.rows),
    )


def render_claim(
    row: EvidenceRow, metric: Metric, statement: Statement = "value"
) -> str:
    statistic = row.statistics
    group = statistic.group_name or "All matching employees"
    if metric == "headcount":
        label = "employees" if isinstance(statistic, HeadcountStatistics) else MetricLabels[metric]
        rank = f"{statement} headcount: " if statement != "value" else ""
        return f"{group} — {rank}{statistic.headcount:,} {label}."
    amount = getattr(statistic, MetricFields[metric])
    rendered = statistic.format_amount(amount)
    label = MetricLabels[metric]
    rank = f"{statement} " if statement != "value" else ""
    return f"{group} — {rank}{label} of {statistic.currency_code} {rendered}."


class ClaimVerifier:
    def __init__(self, evidence: Evidence) -> None:
        self.evidence = evidence
        self.rows = {str(row.id): row for row in evidence.rows}
        self.winners = {row.id for row in evidence.winners()}
        self.claim_ids: set[str] = set()
        self.seen: set[tuple[UUID, Metric, Statement]] = set()

    def check(self, claim: Claim) -> str:
        row = self.rows.get(claim.evidence_id)
        if row is None:
            raise ValueError("Claim does not match report evidence.")
        if isinstance(row.statistics, HeadcountStatistics) and claim.metric != "headcount":
            raise ValueError("Headcount evidence cannot support salary claims.")
        key = (row.id, claim.metric, claim.statement)
        if (
            row.group != claim.group
            or claim.currency != row.statistics.currency_code
            or claim.claim_id in self.claim_ids
            or key in self.seen
        ):
            raise ValueError("Claim does not match report evidence.")
        if claim.statement != "value":
            rank = self.evidence.request.operation
            expected = f"tied {rank}" if len(self.winners) > 1 else rank
            if (
                claim.statement != expected
                or claim.metric != self.evidence.request.metric
                or row.id not in self.winners
            ):
                raise ValueError("Claim does not match the computed ranking.")
        self.claim_ids.add(claim.claim_id)
        self.seen.add(key)
        return render_claim(row, claim.metric, claim.statement)

    def complete(self) -> bool:
        if self.winners:
            return {
                row for row, _, statement in self.seen if statement != "value"
            } == self.winners
        metric = self.evidence.request.metric
        return any(metric is None or claimed == metric for _, claimed, _ in self.seen)


def computed_summary(evidence: Evidence) -> Iterable[str]:
    winners = evidence.winners()
    if winners:
        rank = evidence.request.operation
        statement = f"tied {rank}" if len(winners) > 1 else rank
        for row in winners:
            yield render_claim(row, evidence.request.metric, statement)
        return
    for row in evidence.rows:
        if evidence.request.metric:
            yield render_claim(row, evidence.request.metric)
        else:
            for metric in MetricLabels:
                yield render_claim(row, metric)
