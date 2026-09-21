"""Unit tests for audit log model provenance and parameter tracking."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.models import Base, AuditEvent
from backend.security.audit import AuditService


@pytest.fixture
def audit_service(tmp_path):
    db_file = tmp_path / "test_audit.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    return AuditService(session_factory, database_url=db_url)


def test_audit_records_model_provenance_and_parameters(audit_service):
    event = audit_service.record(
        action="inference.completed",
        resource_type="chat",
        resource_id="session-123",
        user="test-engineer",
        model="qwen2.5:7b",
        detail={
            "model_name": "qwen2.5:7b",
            "model_provider": "ollama",
            "model_params": {
                "temperature": 0.2,
                "top_p": 0.9,
                "max_tokens": 1024,
            },
            "latency_ms": 142.5,
            "prompt_tokens": 350,
            "completion_tokens": 85,
        },
    )

    assert event.model == "qwen2.5:7b"
    assert event.action == "inference.completed"
    assert "model_provider" in event.detail_json
    assert "ollama" in event.detail_json
    assert "temperature" in event.detail_json

    # Check hash chain validity
    verification = audit_service.verify()
    assert verification.valid is True
    assert verification.events == 1
