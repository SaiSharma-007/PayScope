from decimal import Decimal

import pytest

from payscope.agents.evidence import Claim, ClaimVerifier, SummaryRequest, make_evidence
from payscope.analytics.schemas import SalaryReport, SalaryStatistics
from payscope.analytics.schemas import HeadcountReport, HeadcountStatistics
from payscope.agents.evidence import computed_summary, currencies_in


def test_headcount_ranks_all_countries_without_currency_and_preserves_zero_ties():
    request = SummaryRequest(group_by="country", metric="headcount", operation="lowest")
    report = HeadcountReport(revision=1, group_by="country", rows=[
        HeadcountStatistics(group_id=code, group_name=name, headcount=count)
        for code, name, count in [("IN", "India", 12), ("GB", "United Kingdom", 0), ("DE", "Germany", 0)]
    ])
    assert currencies_in(report) == []
    evidence = make_evidence(request, report)
    assert len(evidence.winners()) == 2
    assert evidence.card()["report_type"] == "workforce_headcount"
    assert "currency_code" not in evidence.card()["filters"]
    assert "mean" not in evidence.card()["rows"][0]
    assert list(computed_summary(evidence)) == [
        "United Kingdom — tied lowest headcount: 0 employees.",
        "Germany — tied lowest headcount: 0 employees.",
    ]
    verifier = ClaimVerifier(evidence)
    for index, row in enumerate(evidence.winners()):
        verifier.check(Claim(claim_id=str(index), evidence_id=str(row.id), group=row.group, currency="", metric="headcount", statement="tied lowest"))
    assert verifier.complete()


def test_headcount_refuses_currency_narrowing():
    with pytest.raises(ValueError, match="independent of currency"):
        SummaryRequest(group_by="country", metric="headcount", operation="lowest", currency_code="GBP")


def test_rank_uses_unrounded_values_and_binds_claim_to_original_group():
    report = SalaryReport(
        revision=3,
        group_by="job_title",
        rows=[
            SalaryStatistics(
                group_id=index,
                group_name=name,
                currency_code="INR",
                headcount=20,
                minimum=Decimal(95),
                maximum=Decimal(103),
                mean=Decimal(mean),
                median=Decimal(100),
            )
            for index, name, mean in (
                (1, "Engineer", "100.001"),
                (2, "Analyst", "100.004"),
            )
        ],
    )
    evidence = make_evidence(
        SummaryRequest(
            group_by="job_title",
            currency_code="INR",
            operation="highest",
            metric="average",
        ),
        report,
    )
    first, second = evidence.rows
    assert first.as_payload()["mean"] == second.as_payload()["mean"] == "100.00"
    assert evidence.winners() == (second,)
    claim = Claim(
        claim_id="1",
        evidence_id=str(second.id),
        group=first.group,
        currency="INR",
        metric="average",
        statement="highest",
    )
    verifier = ClaimVerifier(evidence)
    with pytest.raises(ValueError, match="evidence"):
        verifier.check(claim)
    assert "Analyst" in verifier.check(claim.model_copy(update={"group": second.group}))
    assert verifier.complete()
