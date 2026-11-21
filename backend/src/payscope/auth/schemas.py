from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, StringConstraints


class SignIn(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)]
    password: SecretStr = Field(min_length=1, max_length=1024)


class HrUser(BaseModel):
    id: UUID
    email: str
    display_name: str
    manage_agent_prompts: bool = False


class SessionResponse(BaseModel):
    user: HrUser
    expires_at: datetime
    csrf_token: str = Field(repr=False)
