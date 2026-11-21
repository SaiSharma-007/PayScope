import pytest
from pydantic import ValidationError
from payscope.agents.saved import Metadata, SaveReport
from uuid import uuid4


def test_saved_metadata_requires_a_real_title_and_limits_description():
    assert Metadata(title="  Country headcounts  ").title == "Country headcounts"
    with pytest.raises(ValidationError):
        Metadata(title="   ")
    with pytest.raises(ValidationError):
        Metadata(title="Title", description="x" * 2001)


def test_client_cannot_supply_or_edit_snapshot_figures():
    with pytest.raises(ValidationError):
        SaveReport(source_run_id=uuid4(), title="Title", report={"rows": []})
    with pytest.raises(ValidationError):
        Metadata(title="Title", summary="Forged summary")


def test_chart_preferences_are_constrained():
    value = SaveReport(source_run_id=uuid4(), title="Title", chart_view={"measure": "headcount", "sort": "ascending"})
    assert value.chart_view.measure == "headcount"
    with pytest.raises(ValidationError):
        SaveReport(source_run_id=uuid4(), title="Title", chart_view={"measure": "script", "sort": "ascending"})
