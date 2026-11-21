from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

AgentKey = Literal["pay_analyst", "answer_writer"]
RunKind = Literal["question", "clarification", "retry"]
TerminalStatus = Literal[
    "completed",
    "awaiting_clarification",
    "unsupported",
    "failed",
    "cancelled",
    "interrupted",
]
RunStatus = Literal["queued", "running", TerminalStatus]

VersionNumber = Annotated[int, Field(gt=0, le=2_147_483_647)]
EditRevision = Annotated[int, Field(ge=0, le=9_223_372_036_854_775_807)]
ChangeNote = Annotated[str, StringConstraints(max_length=500, pattern=r"^[^\x00]*$")]


class PromptVersion(BaseModel):
    version: int
    author_id: UUID | None
    author_name: str | None
    published_by: UUID | None
    published_at: datetime
    change_note: str


class PromptVersionBody(PromptVersion):
    body: str


class PromptDraft(BaseModel):
    author_id: UUID
    author_name: str
    updated_at: datetime
    change_note: str


class PromptDraftBody(PromptDraft):
    body: str


class PromptSummary(BaseModel):
    agent_key: AgentKey
    edit_revision: int
    active: PromptVersion
    draft: PromptDraft | None


class PromptDetail(PromptSummary):
    draft: PromptDraftBody | None


class PromptVersionPage(BaseModel):
    items: list[PromptVersion]
    next_before_version: int | None


class PromptEdit(BaseModel):
    expected_revision: EditRevision


class SavePromptDraft(PromptEdit):
    body: Annotated[str, StringConstraints(max_length=12000, pattern=r"^[^\x00]*$")]
    change_note: ChangeNote = ""

    @field_validator("body")
    @classmethod
    def require_content(cls, body: str) -> str:
        if not body.strip():
            raise ValueError("Enter a prompt body.")
        return body


class RestorePromptDraft(PromptEdit):
    version: VersionNumber
    change_note: ChangeNote = ""


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: UUID | None = None
    question: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=2000, pattern=r"^[^\x00]*$"
        ),
    ]
    kind: RunKind = "question"
    parent_run_id: UUID | None = None


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    active_run_id: UUID | None


class ConversationPage(BaseModel):
    items: list[ConversationSummary]
    next_offset: int | None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    structured_content: dict | None
    is_partial: bool
    created_at: datetime


class ChatTurn(BaseModel):
    run_id: UUID
    turn_number: int
    kind: RunKind
    parent_run_id: UUID | None
    status: RunStatus
    messages: list[ChatMessage]
    events: list[dict] = Field(default_factory=list)


class ConversationDetail(ConversationSummary):
    turns: list[ChatTurn]
    next_before_turn: int | None
