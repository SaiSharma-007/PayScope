from types import SimpleNamespace
import pytest
from fastapi import HTTPException, Response
from sqlalchemy.dialects import postgresql
from payscope.agents.observability import base, columns, model_usage, require_observer


def test_observation_is_independent_of_chat_visibility_and_hides_credentials():
    query = str(base.compile(dialect=postgresql.dialect()))
    assert 'deleted_at IS NULL' not in query
    assert 'execution_owner_token' not in query
    assert 'auth_session_id' not in query
    assert 'request_hash' not in query
    assert 'id' in [c.name for c in columns]


def test_usage_counts_all_attempts_and_does_not_invent_missing_tokens():
    assert model_usage([{'input_tokens': 2, 'output_tokens': 3}, {'input_tokens': 4}]) == {'model_calls': 2, 'input_tokens': 6, 'output_tokens': None}
    assert model_usage([])['input_tokens'] is None


def test_observer_permission_is_explicit():
    import asyncio
    session = SimpleNamespace(response=SimpleNamespace(user=SimpleNamespace(view_agent_observability=False)))
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_observer(session, Response()))
    assert error.value.status_code == 403
    session.response.user.view_agent_observability = True
    response = Response()
    asyncio.run(require_observer(session, response))
    assert response.headers['Cache-Control'] == 'no-store'
