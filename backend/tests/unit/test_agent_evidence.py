from decimal import Decimal

import pytest

from payscope.agents.evidence import Claim, ClaimVerifier, SummaryRequest, make_evidence
from payscope.analytics.schemas import SalaryReport, SalaryStatistics


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
