"""Unit tests for insufficient evidence abstention."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.chat.service import ChatService, ChatTurnResult
from backend.models.router import ModelRouter, ResolvedModel
from backend.chat.sessions import ChatSessionStore
from backend.security.audit import AuditService


@pytest.mark.asyncio
async def test_chat_service_abstains_when_grounding_required_and_no_evidence():
    mock_router = MagicMock(spec=ModelRouter)
    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock()
    resolved = ResolvedModel(model="qwen2.5:7b", provider_name="ollama", provider=mock_provider)
    mock_router.resolve = AsyncMock(return_value=resolved)

    session_store = ChatSessionStore()
    mock_audit = MagicMock(spec=AuditService)

    service = ChatService(
        router=mock_router,
        sessions=session_store,
        audit=mock_audit,
        retrieval=None,  # No retrieval service available -> evidence empty
    )

    result = await service.run_turn(
        message="What is the maintenance history of pump P-999?",
        use_rag=True,
        require_grounding=True,
    )

    assert "Insufficient evidence" in result.response
    # Verify provider was NOT called to invent hallucinated answers
    mock_provider.chat.assert_not_called()
    assert result.evidence == []
