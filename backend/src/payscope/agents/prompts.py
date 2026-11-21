from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from payscope.agents.schemas import (
    AgentKey,
    PromptDetail,
    PromptDraftBody,
    PromptEdit,
    PromptSummary,
    PromptVersion,
    PromptVersionBody,
    PromptVersionPage,
    RestorePromptDraft,
    SavePromptDraft,
    VersionNumber,
)
from payscope.auth.router import Session, VerifiedSession
from payscope.database import DatabaseSession
from payscope.models import agent_prompt_catalog as catalog
from payscope.models import agent_prompt_versions as versions
from payscope.models import hr_users


async def require_prompt_admin(session: Session) -> None:
    if not session.response.user.manage_agent_prompts:
        raise HTTPException(
            403,
            detail={
                "code": "PROMPT_CATALOG_FORBIDDEN",
                "message": "Prompt administration is restricted.",
            },
            headers={"Cache-Control": "no-store"},
        )


router = APIRouter(
    prefix="/admin/agent-prompts",
    tags=["Agent prompt administration"],
    dependencies=[Depends(require_prompt_admin)],
)

version_query = sa.select(
    versions.c.agent_key,
    versions.c.version,
    versions.c.change_note,
    versions.c.author_id,
    versions.c.published_by,
    versions.c.published_at,
    hr_users.c.display_name.label("author_name"),
).outerjoin(hr_users, versions.c.author_id == hr_users.c.id)
active = version_query.subquery()
draft_author = hr_users.alias("draft_author")
catalog_query = (
    sa.select(
        catalog, *active.c, draft_author.c.display_name.label("draft_author_name")
    )
    .join_from(
        catalog,
        active,
        sa.and_(
            catalog.c.agent_key == active.c.agent_key,
            catalog.c.active_version == active.c.version,
        ),
    )
    .outerjoin(draft_author, draft_author.c.id == catalog.c.draft_author_id)
)


def prompt_detail(row: sa.RowMapping) -> PromptDetail:
    return PromptDetail(
        agent_key=row[catalog.c.agent_key],
        edit_revision=row.edit_revision,
        active=PromptVersion.model_validate(row),
        draft=PromptDraftBody(
            body=row.draft_body,
            change_note=row.draft_change_note,
            author_id=row.draft_author_id,
            author_name=row.draft_author_name,
            updated_at=row.draft_updated_at,
        )
        if row.draft_body is not None
        else None,
    )


async def load_prompt(database: AsyncSession, agent_key: AgentKey) -> PromptDetail:
    result = await database.execute(
        catalog_query.where(catalog.c.agent_key == agent_key)
    )
    return prompt_detail(result.mappings().one())


async def load_version(
    database: AsyncSession,
    agent_key: AgentKey,
    version: int,
) -> PromptVersionBody:
    result = await database.execute(
        version_query.add_columns(versions.c.body).where(
            versions.c.agent_key == agent_key, versions.c.version == version
        )
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(
            404,
            detail={
                "code": "PROMPT_VERSION_NOT_FOUND",
                "message": "Prompt version not found.",
            },
        )
    return PromptVersionBody.model_validate(row)


async def lock_prompt(
    database: AsyncSession,
    agent_key: AgentKey,
    expected_revision: int,
) -> sa.RowMapping:
    result = await database.execute(
        catalog.select().where(catalog.c.agent_key == agent_key).with_for_update()
    )
    row = result.mappings().one()
    if row.edit_revision != expected_revision:
        raise HTTPException(
            409,
            detail={
                "code": "PROMPT_CHANGED",
                "message": "This prompt changed. Load the latest version before saving.",
                "current_revision": row.edit_revision,
            },
        )
    return row


async def update_prompt(
    database: AsyncSession, agent_key: AgentKey, **changes
) -> PromptDetail:
    await database.execute(
        catalog.update()
        .where(catalog.c.agent_key == agent_key)
        .values(
            **changes,
            edit_revision=catalog.c.edit_revision + 1,
        )
    )
    updated = await load_prompt(database, agent_key)
    await database.commit()
    return updated


@router.get("")
async def list_prompts(database: DatabaseSession) -> list[PromptSummary]:
    result = await database.execute(catalog_query.order_by(catalog.c.agent_key))
    return [prompt_detail(row) for row in result.mappings()]


@router.get("/{agent_key}")
async def get_prompt(agent_key: AgentKey, database: DatabaseSession) -> PromptDetail:
    return await load_prompt(database, agent_key)


@router.get("/{agent_key}/versions")
async def list_versions(
    agent_key: AgentKey,
    database: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    before_version: Annotated[int | None, Query(gt=0, le=2_147_483_647)] = None,
) -> PromptVersionPage:
    query = version_query.where(versions.c.agent_key == agent_key)
    if before_version is not None:
        query = query.where(versions.c.version < before_version)
    result = await database.execute(
        query.order_by(versions.c.version.desc()).limit(limit + 1)
    )
    rows = result.mappings().all()
    return PromptVersionPage(
        items=[PromptVersion.model_validate(row) for row in rows[:limit]],
        next_before_version=rows[limit - 1].version if len(rows) > limit else None,
    )


@router.get("/{agent_key}/versions/{version}")
async def get_version(
    agent_key: AgentKey,
    version: VersionNumber,
    database: DatabaseSession,
) -> PromptVersionBody:
    return await load_version(database, agent_key, version)


@router.put("/{agent_key}/draft")
async def save_draft(
    agent_key: AgentKey,
    edit: SavePromptDraft,
    session: VerifiedSession,
    database: DatabaseSession,
) -> PromptDetail:
    await lock_prompt(database, agent_key, edit.expected_revision)
    return await update_prompt(
        database,
        agent_key,
        draft_body=edit.body,
        draft_change_note=edit.change_note,
        draft_author_id=session.user_id,
        draft_updated_at=sa.func.clock_timestamp(),
    )


@router.post("/{agent_key}/draft/restore")
async def restore_draft(
    agent_key: AgentKey,
    edit: RestorePromptDraft,
    session: VerifiedSession,
    database: DatabaseSession,
) -> PromptDetail:
    await lock_prompt(database, agent_key, edit.expected_revision)
    source = await load_version(database, agent_key, edit.version)
    return await update_prompt(
        database,
        agent_key,
        draft_body=source.body,
        draft_change_note=edit.change_note or f"Restored from v{source.version}",
        draft_author_id=session.user_id,
        draft_updated_at=sa.func.clock_timestamp(),
    )


@router.post("/{agent_key}/publish")
async def publish_prompt(
    agent_key: AgentKey,
    edit: PromptEdit,
    session: VerifiedSession,
    database: DatabaseSession,
) -> PromptDetail:
    draft = await lock_prompt(database, agent_key, edit.expected_revision)
    if draft.draft_body is None:
        raise HTTPException(
            409,
            detail={
                "code": "PROMPT_DRAFT_REQUIRED",
                "message": "Save a draft before publishing.",
            },
        )
    version = draft.active_version + 1
    await database.execute(
        versions.insert().values(
            agent_key=agent_key,
            version=version,
            body=draft.draft_body,
            change_note=draft.draft_change_note,
            author_id=draft.draft_author_id,
            published_by=session.user_id,
            published_at=sa.func.clock_timestamp(),
        )
    )
    return await update_prompt(
        database,
        agent_key,
        active_version=version,
        draft_body=None,
        draft_change_note=None,
        draft_author_id=None,
        draft_updated_at=None,
    )
