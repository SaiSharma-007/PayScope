from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Query, Response

from payscope.agents.runs import ACTIVE
from payscope.agents.schemas import (
    ChatMessage,
    ChatTurn,
    ConversationDetail,
    ConversationPage,
    ConversationSummary,
)
from payscope.auth.router import Session, VerifiedSession
from payscope.database import DatabaseSession
from payscope.models import agent_conversations as conversations
from payscope.models import agent_events as events
from payscope.models import agent_messages as messages
from payscope.models import agent_runs as runs
from payscope.models import saved_reports

router = APIRouter(prefix="/agent/conversations", tags=["Agent conversations"])
PageSize = Annotated[int, Query(ge=1, le=100)]

active_run = (
    sa.select(runs.c.id)
    .where(
        runs.c.conversation_id == conversations.c.id,
        ACTIVE,
    )
    .correlate(conversations)
    .scalar_subquery()
)
summary_columns = (
    conversations.c.id,
    conversations.c.title,
    conversations.c.created_at,
    conversations.c.updated_at,
    active_run.label("active_run_id"),
)


@router.get("")
async def list_conversations(
    session: Session,
    database: DatabaseSession,
    limit: PageSize = 20,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
) -> ConversationPage:
    result = await database.execute(
        sa.select(*summary_columns)
        .where(
            conversations.c.user_id == session.user_id,
            conversations.c.deleted_at.is_(None),
        )
        .order_by(conversations.c.updated_at.desc(), conversations.c.id.desc())
        .limit(limit + 1)
        .offset(offset)
    )
    rows = result.mappings().all()
    return ConversationPage(
        items=[ConversationSummary.model_validate(row) for row in rows[:limit]],
        next_offset=offset + limit if len(rows) > limit else None,
    )


@router.get("/{conversation_id}")
async def conversation_detail(
    conversation_id: UUID,
    session: Session,
    database: DatabaseSession,
    limit: PageSize = 20,
    before_turn: Annotated[
        int | None, Query(gt=0, le=9_223_372_036_854_775_807)
    ] = None,
) -> ConversationDetail:
    turns = sa.select(
        runs.c.id.label("run_id"),
        runs.c.turn_number,
        runs.c.kind,
        runs.c.parent_run_id,
        runs.c.status,
    ).where(
        runs.c.conversation_id == conversation_id, runs.c.user_id == session.user_id
    )
    if before_turn is not None:
        turns = turns.where(runs.c.turn_number < before_turn)
    page = turns.order_by(runs.c.turn_number.desc()).limit(limit + 1).subquery()
    result = await database.execute(
        sa.select(
            *summary_columns,
            *page.c,
            messages.c.role,
            messages.c.text,
            messages.c.structured_content,
            messages.c.is_partial,
            messages.c.created_at.label("message_created_at"),
        )
        .select_from(conversations)
        .outerjoin(page, sa.true())
        .outerjoin(
            messages,
            messages.c.run_id == page.c.run_id,
        )
        .where(
            conversations.c.id == conversation_id,
            conversations.c.user_id == session.user_id,
            conversations.c.deleted_at.is_(None),
        )
        .order_by(page.c.turn_number.desc(), messages.c.role.desc())
    )
    rows = result.mappings().all()
    if not rows:
        raise HTTPException(
            404,
            detail={
                "code": "CONVERSATION_NOT_FOUND",
                "message": "Conversation not found.",
            },
        )

    by_turn = {}
    for row in rows:
        if row.turn_number is None:
            continue
        if row.turn_number not in by_turn:
            by_turn[row.turn_number] = ChatTurn.model_validate(
                dict(row) | {"messages": []}
            )
        if row.role is not None:
            by_turn[row.turn_number].messages.append(
                ChatMessage(
                    role=row.role,
                    text=row.text,
                    structured_content=row.structured_content,
                    is_partial=row.is_partial,
                    created_at=row.message_created_at,
                )
            )
    chat_turns = list(by_turn.values())
    visible_turns = chat_turns[:limit]
    if visible_turns:
        saved = dict((await database.execute(sa.select(saved_reports.c.source_run_id, saved_reports.c.id).where(saved_reports.c.user_id == session.user_id, saved_reports.c.deleted_at.is_(None), saved_reports.c.source_run_id.in_([turn.run_id for turn in visible_turns])))).tuples().all())
        for turn in visible_turns:
            turn.saved_report_id = saved.get(turn.run_id)
        activity = await database.execute(
            events.select()
            .where(
                events.c.run_id.in_([turn.run_id for turn in visible_turns]),
                events.c.event_type.not_in(("token", "report_ready")),
            )
            .order_by(events.c.run_id, events.c.sequence)
        )
        by_run = {turn.run_id: turn for turn in visible_turns}
        for item in activity.mappings():
            by_run[item.run_id].events.append(
                {
                    "event_id": str(item.event_id),
                    "run_id": str(item.run_id),
                    "sequence": item.sequence,
                    "timestamp": item.created_at.isoformat(),
                    "type": item.event_type,
                    "agent_name": item.agent_name,
                    "call_id": str(item.call_id) if item.call_id else None,
                    "payload": item.payload,
                }
            )
    return ConversationDetail(
        **ConversationSummary.model_validate(rows[0]).model_dump(),
        turns=list(reversed(visible_turns)),
        next_before_turn=chat_turns[limit - 1].turn_number
        if len(chat_turns) > limit
        else None,
    )


async def set_deleted(database, conversation_id, user_id, deleted):
    # Serialize deletion with admission's conversation lock.
    await database.rollback()
    async with database.begin():
        conversation = await database.scalar(
            sa.select(conversations.c.id)
            .where(conversations.c.id == conversation_id, conversations.c.user_id == user_id)
            .with_for_update()
        )
        if conversation is None:
            raise HTTPException(404, detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversation not found."})
        if deleted and await database.scalar(
            sa.select(runs.c.id).where(runs.c.conversation_id == conversation_id, ACTIVE).limit(1)
        ):
            raise HTTPException(409, detail={"code": "CONVERSATION_BUSY", "message": "Stop the active response before deleting this chat."})
        await database.execute(
            conversations.update()
            .where(conversations.c.id == conversation_id)
            .values(deleted_at=sa.func.clock_timestamp() if deleted else None)
        )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: UUID, session: VerifiedSession, database: DatabaseSession):
    await set_deleted(database, conversation_id, session.user_id, True)
    return Response(status_code=204)


@router.post("/{conversation_id}/restore", status_code=204)
async def restore_conversation(conversation_id: UUID, session: VerifiedSession, database: DatabaseSession):
    await set_deleted(database, conversation_id, session.user_id, False)
    return Response(status_code=204)
