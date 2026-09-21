import logging
from backend.logging_config import SensitiveDataFilter, redact_text


def test_redact_text_patterns():
    # API key
    msg = "Failed with api_key='secret_key_12345678'"
    redacted = redact_text(msg)
    assert "secret_key_12345678" not in redacted
    assert "[REDACTED]" in redacted

    # OpenAI sk- key
    msg = "Using key sk-12345678901234567890abcdef in header"
    redacted = redact_text(msg)
    assert "sk-12345678901234567890abcdef" not in redacted
    assert "[REDACTED_API_KEY]" in redacted

    # Bearer token
    msg = "Sending Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    redacted = redact_text(msg)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted


def test_filter_redacts_log_record():
    filt = SensitiveDataFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="test.py",
        lineno=10,
        msg="Error connecting with password='SuperSecretPassword123!'",
        args=(),
        exc_info=None,
    )
    record.exc_text = "Traceback (most recent call last):\n  File 'x.py'\nKeyError: api_key='secret123456789'"

    assert filt.filter(record) is True
    assert "SuperSecretPassword123!" not in record.msg
    assert "secret123456789" not in record.exc_text
