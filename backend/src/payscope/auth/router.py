import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.security import APIKeyCookie

from payscope.auth import service
from payscope.auth.schemas import SessionResponse, SignIn
from payscope.auth.service import ActiveSession
from payscope.database import DatabaseSession

router = APIRouter(prefix="/auth", tags=["Authentication"])
SESSION_COOKIE = "payscope_session"
COOKIE_PATH = "/api"
session_cookie = APIKeyCookie(name=SESSION_COOKIE, scheme_name="HrSession", auto_error=False)


async def require_session(
    database: DatabaseSession,
    response: Response,
    session_token: Annotated[str | None, Depends(session_cookie)],
) -> ActiveSession:
    session = await service.find_session(database, session_token) if session_token else None
    if session is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "SESSION_REQUIRED", "message": "Sign in to continue."},
            headers={"Cache-Control": "no-store"},
        )
    response.headers["Cache-Control"] = "no-store"
    return session


Session = Annotated[ActiveSession, Depends(require_session)]


async def require_csrf(
    session: Session, csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None
) -> ActiveSession:
    if not csrf or not hmac.compare_digest(service.token_hash(csrf), session.csrf_hash):
        raise HTTPException(
            status_code=403,
            detail={"code": "INVALID_CSRF_TOKEN", "message": "A valid CSRF token is required."},
            headers={"Cache-Control": "no-store"},
        )
    return session


VerifiedSession = Annotated[ActiveSession, Depends(require_csrf)]


@router.post("/sign-in")
async def create_session(
    credentials: SignIn, request: Request, response: Response, database: DatabaseSession
) -> SessionResponse:
    content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Sign-in requires application/json.")

    ttl_seconds = request.app.state.settings.session_ttl_seconds
    result = await service.sign_in(database, credentials, ttl_seconds)
    if result is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."},
            headers={"Cache-Control": "no-store"},
        )
    session_token, session = result
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=ttl_seconds,
        path=COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return session


@router.get("/session")
async def current_session(session: Session) -> SessionResponse:
    return session.response


@router.post("/sign-out", status_code=204)
async def sign_out(session: VerifiedSession, database: DatabaseSession) -> Response:
    await service.revoke_session(database, session.id)
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        SESSION_COOKIE, path=COOKIE_PATH, secure=True, httponly=True, samesite="lax"
    )
    return response
