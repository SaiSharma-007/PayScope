import asyncio
import hmac
from dataclasses import dataclass, field
from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from payscope.auth.schemas import HrUser, SessionResponse, SignIn
from payscope.models import auth_sessions, hr_users

USER_COLUMNS = (
    hr_users.c.id,
    hr_users.c.email,
    hr_users.c.display_name,
    hr_users.c.manage_agent_prompts,
    hr_users.c.view_agent_observability,
)
PASSWORD_HASHER = PasswordHasher()
SESSION_TOKEN_BYTES = 32


@dataclass(frozen=True, slots=True)
class ActiveSession:
    id: UUID
    response: SessionResponse
    csrf_hash: bytes = field(repr=False)

    @property
    def user_id(self) -> UUID:
        return self.response.user.id


def token_hash(token: str) -> bytes:
    return sha256(token.encode()).digest()


def csrf_token(session_token: str) -> str:
    return hmac.new(session_token.encode(), b"payscope:csrf", sha256).hexdigest()


async def sign_in(
    database: AsyncSession, credentials: SignIn, ttl_seconds: int
) -> tuple[str, SessionResponse] | None:
    user = (
        (
            await database.execute(
                select(*USER_COLUMNS, hr_users.c.password_hash).where(
                    hr_users.c.email == credentials.email.lower(), hr_users.c.is_active.is_(True)
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    await database.rollback()

    password = credentials.password.get_secret_value()
    if user is None:
        await asyncio.to_thread(PASSWORD_HASHER.hash, password)
        return None
    try:
        await asyncio.to_thread(PASSWORD_HASHER.verify, user["password_hash"], password)
    except (VerificationError, InvalidHashError):
        return None

    session_token = token_urlsafe(SESSION_TOKEN_BYTES)
    csrf = csrf_token(session_token)
    expires_at = await database.scalar(
        auth_sessions.insert()
        .values(
            id=uuid4(),
            user_id=user["id"],
            token_hash=token_hash(session_token),
            csrf_token_hash=token_hash(csrf),
            expires_at=func.now() + timedelta(seconds=ttl_seconds),
        )
        .returning(auth_sessions.c.expires_at)
    )
    await database.commit()
    return session_token, SessionResponse(
        user=HrUser(**user), expires_at=expires_at, csrf_token=csrf
    )


async def find_session(database: AsyncSession, session_token: str) -> ActiveSession | None:
    session = (
        (
            await database.execute(
                select(
                    *USER_COLUMNS,
                    auth_sessions.c.id.label("session_id"),
                    auth_sessions.c.expires_at,
                    auth_sessions.c.csrf_token_hash,
                )
                .join_from(auth_sessions, hr_users)
                .where(
                    auth_sessions.c.token_hash == token_hash(session_token),
                    auth_sessions.c.revoked_at.is_(None),
                    auth_sessions.c.expires_at > func.now(),
                    hr_users.c.is_active.is_(True),
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if session is None:
        return None
    return ActiveSession(
        session["session_id"],
        SessionResponse(
            user=HrUser(**session),
            expires_at=session["expires_at"],
            csrf_token=csrf_token(session_token),
        ),
        session["csrf_token_hash"],
    )


async def revoke_session(database: AsyncSession, session_id: UUID) -> None:
    await database.execute(
        auth_sessions.update()
        .where(auth_sessions.c.id == session_id, auth_sessions.c.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )
    await database.commit()
