from uuid import UUID, uuid4
from typing import Annotated, Literal
import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy.dialects.postgresql import insert
from payscope.auth.router import Session, VerifiedSession
from payscope.database import DatabaseSession
from payscope.models import saved_reports as reports, agent_runs as runs, agent_messages as messages, agent_conversations as chats

router = APIRouter(prefix="/saved-reports", tags=["Saved reports"])

class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)

    @field_validator("title")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Enter a title")
        return value.strip()

class ChartView(BaseModel):
    measure: Literal["comparison", "mean", "median", "minimum", "maximum", "headcount"]
    sort: Literal["ascending", "descending", "name"]

class SaveReport(Metadata):
    source_run_id: UUID
    chart_view: ChartView | None = None

async def owned(db, report_id, user_id, deleted=False):
    row = (await db.execute(sa.select(reports).where(reports.c.id == report_id, reports.c.user_id == user_id, *([] if deleted else [reports.c.deleted_at.is_(None)])))).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, detail="Saved report not found")
    return row

@router.post("")
async def save(body: SaveReport, session: VerifiedSession, database: DatabaseSession):
    await database.rollback()
    async with database.begin():
        source = (await database.execute(sa.select(runs, messages.c.structured_content, messages.c.text).join(chats).join(messages, sa.and_(messages.c.run_id == runs.c.id, messages.c.role == "assistant")).where(runs.c.id == body.source_run_id, runs.c.user_id == session.user_id, chats.c.deleted_at.is_(None)).with_for_update(of=chats))).mappings().one_or_none()
        if source is None:
            raise HTTPException(404, detail="Source report not found")
        payload = source.structured_content or {}
        report = payload.get("report")
        if source.status != "completed" or not report or report.get("report_type") not in ("annual_gross_base", "workforce_headcount"):
            raise HTTPException(409, detail="Only completed reports can be saved")
        if report.get("report_type") == "workforce_headcount" and body.chart_view and body.chart_view.measure != "headcount":
            raise HTTPException(422, detail="Headcount reports require an employee-count chart")
        await database.execute(insert(reports).values(id=uuid4(), user_id=session.user_id, source_run_id=source.id, source_conversation_id=source.conversation_id, title=body.title, description=body.description, report=report, summary=source.text, generated_at=source.finished_at, chart_view=body.chart_view.model_dump() if body.chart_view else {}).on_conflict_do_update(constraint="uq_saved_report_source", set_={"deleted_at": None}))
        return (await database.execute(sa.select(reports).where(reports.c.user_id == session.user_id, reports.c.source_run_id == source.id))).mappings().one()

@router.get("")
async def listing(session: Session, database: DatabaseSession, q: str = "", report_type: str | None = None, offset: Annotated[int, Query(ge=0)] = 0):
    query = sa.select(reports).where(reports.c.user_id == session.user_id, reports.c.deleted_at.is_(None))
    if q:
        query = query.where(sa.or_(reports.c.title.icontains(q, autoescape=True), reports.c.description.icontains(q, autoescape=True)))
    if report_type:
        query = query.where(reports.c.report["report_type"].astext == report_type)
    rows = (await database.execute(query.order_by(reports.c.saved_at.desc(), reports.c.id).offset(offset).limit(21))).mappings().all()
    return {"items": rows[:20], "next_offset": offset + 20 if len(rows) > 20 else None}

@router.get("/{report_id}")
async def detail(report_id: UUID, session: Session, database: DatabaseSession):
    row = await owned(database, report_id, session.user_id)
    available = await database.scalar(sa.select(chats.c.id).where(chats.c.id == row.source_conversation_id, chats.c.user_id == session.user_id, chats.c.deleted_at.is_(None)))
    return dict(row) | {"source_available": available is not None}

@router.patch("/{report_id}")
async def edit(report_id: UUID, body: Metadata, session: VerifiedSession, database: DatabaseSession):
    await owned(database, report_id, session.user_id)
    await database.execute(reports.update().where(reports.c.id == report_id).values(**body.model_dump()))
    await database.commit()
    return await owned(database, report_id, session.user_id)

@router.delete("/{report_id}", status_code=204)
async def delete(report_id: UUID, session: VerifiedSession, database: DatabaseSession):
    await owned(database, report_id, session.user_id, True)
    await database.execute(reports.update().where(reports.c.id == report_id).values(deleted_at=sa.func.now()))
    await database.commit()
    return Response(status_code=204)

@router.post("/{report_id}/restore", status_code=204)
async def restore(report_id: UUID, session: VerifiedSession, database: DatabaseSession):
    await owned(database, report_id, session.user_id, True)
    await database.execute(reports.update().where(reports.c.id == report_id).values(deleted_at=None))
    await database.commit()
    return Response(status_code=204)
