from pydantic import AwareDatetime
from typing import Annotated, Literal
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from payscope.auth.router import Session
from payscope.database import DatabaseSession
from payscope.models import agent_runs as runs, agent_conversations as chats, agent_events as events, agent_messages as messages, agent_tool_calls as tools, hr_users

async def require_observer(session: Session, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    if not session.response.user.view_agent_observability:
        raise HTTPException(403, detail={'message': 'Agent observability access is restricted.'})

router = APIRouter(prefix='/admin/agent-runs', tags=['Agent observability'], dependencies=[Depends(require_observer)])

# Explicit allowlist keeps execution credentials out of every admin response.
columns = [runs.c[name] for name in ('id','conversation_id','user_id','turn_number','kind','parent_run_id','status','pay_analyst_version','answer_writer_version','runtime_fingerprint','runtime_limits','created_at','started_at','finished_at','last_event_sequence')]
base = sa.select(*columns, chats.c.deleted_at.label('source_deleted_at'), chats.c.title, hr_users.c.display_name.label('owner')).join(chats, runs.c.conversation_id == chats.c.id).join(hr_users, runs.c.user_id == hr_users.c.id)


def model_usage(payloads):
    calls = list(payloads)
    return {'model_calls': len(calls), 'input_tokens': sum(p['input_tokens'] for p in calls) if calls and all(p.get('input_tokens') is not None for p in calls) else None, 'output_tokens': sum(p['output_tokens'] for p in calls) if calls and all(p.get('output_tokens') is not None for p in calls) else None}


@router.get('')
async def listing(database: DatabaseSession, status: Literal['completed','failed','cancelled','interrupted','awaiting_clarification','unsupported','queued','running'] | None = None, owner: UUID | None = None, role: Literal['pay_analyst','answer_writer'] | None = None, version: Annotated[int | None, Query(gt=0)] = None, source: Literal['all','available','deleted'] = 'all', model: Annotated[str | None, Query(max_length=200)] = None, run_id: UUID | None = None, start: AwareDatetime | None = None, end: AwareDatetime | None = None, before: AwareDatetime | None = None, before_id: UUID | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 30):
    query = base
    if start and end and start > end: raise HTTPException(422, detail='Start must precede end.')
    if status: query = query.where(runs.c.status == status)
    if owner: query = query.where(runs.c.user_id == owner)
    if version is not None:
        if not role: raise HTTPException(422, detail='Choose a prompt role with a version.')
        query = query.where(runs.c[f'{role}_version'] == version)
    if source != 'all': query = query.where(chats.c.deleted_at.is_not(None) if source == 'deleted' else chats.c.deleted_at.is_(None))
    if model: query = query.where(sa.exists(sa.select(1).where(events.c.run_id == runs.c.id, events.c.event_type == 'model_completed', events.c.payload['model'].astext == model)))
    if run_id: query = query.where(runs.c.id == run_id)
    if start: query = query.where(runs.c.created_at >= start)
    if end: query = query.where(runs.c.created_at <= end)
    filtered = query.subquery()
    seconds = sa.extract('epoch', filtered.c.finished_at - filtered.c.started_at)
    totals = (await database.execute(sa.select(filtered.c.status, sa.func.count().label('count'), sa.func.avg(seconds).label('average_seconds'), sa.func.count(seconds).label('duration_samples')).group_by(filtered.c.status))).mappings().all()
    if before:
        if not before_id: raise HTTPException(422, detail='A complete page cursor is required.')
        query = query.where(sa.tuple_(runs.c.created_at, runs.c.id) < sa.tuple_(before, before_id))
    rows = (await database.execute(query.order_by(runs.c.created_at.desc(), runs.c.id.desc()).limit(limit + 1))).mappings().all()
    page = [dict(row) for row in rows[:limit]]
    if page:
        usage = (await database.execute(sa.select(events.c.run_id, events.c.payload).where(events.c.run_id.in_([r['id'] for r in page]), events.c.event_type == 'model_completed'))).all()
        for row in page: row.update(model_usage(p for rid, p in usage if rid == row['id']))
    return {'summary': totals, 'items': page, 'next': {'before': page[-1]['created_at'], 'before_id': page[-1]['id']} if len(rows) > limit else None}


async def load(database, run_id):
    row = (await database.execute(base.where(runs.c.id == run_id))).mappings().one_or_none()
    if row is None: raise HTTPException(404, detail={'message': 'Run not found.'})
    return dict(row)


@router.get('/{run_id}')
async def detail(run_id: UUID, database: DatabaseSession):
    row = await load(database, run_id)
    row['messages'] = (await database.execute(sa.select(messages.c.role, messages.c.text, messages.c.structured_content, messages.c.is_partial).where(messages.c.run_id == run_id))).mappings().all()
    return row


@router.get('/{run_id}/events')
async def timeline(run_id: UUID, database: DatabaseSession, after: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=200)] = 100):
    await load(database, run_id)
    rows = (await database.execute(events.select().where(events.c.run_id == run_id, events.c.sequence > after, events.c.event_type.not_in(('token','report_ready'))).order_by(events.c.sequence).limit(limit + 1))).mappings().all()
    return {'items': rows[:limit], 'next_after': rows[limit-1]['sequence'] if len(rows) > limit else None}


@router.get('/{run_id}/tools')
async def evidence(run_id: UUID, database: DatabaseSession):
    await load(database, run_id)
    return (await database.execute(tools.select().where(tools.c.run_id == run_id).order_by(tools.c.attempt_number).limit(100))).mappings().all()
