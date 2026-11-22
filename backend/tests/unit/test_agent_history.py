import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from payscope.agents.history import conversation_detail


def test_unavailable_chat_links_return_the_same_problem():
    database = AsyncMock()
    database.execute.return_value = Mock()
    database.execute.return_value.mappings.return_value.all.return_value = []
    session = SimpleNamespace(user_id=uuid4())
    missing_id = "f1c97cee-2d1c-485c-ae29-ebcb5cf5ce91"

    for chat_id, expected_queries in ((missing_id + "\\", 0), (missing_id, 1)):
        with pytest.raises(HTTPException) as failure:
            asyncio.run(conversation_detail(chat_id, session, database, limit=20))

        assert database.execute.await_count == expected_queries
        assert failure.value.status_code == 404
        assert failure.value.headers == {"Cache-Control": "no-store"}
        assert failure.value.detail == {
            "code": "CONVERSATION_NOT_FOUND",
            "message": "Conversation not found.",
        }
