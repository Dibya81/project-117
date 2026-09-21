"""Ed25519 artifact signing: the utility, the service path, and the tamper test.

The acceptance test is the pair at the top: sign a file and verify it, then
modify **one byte** and require verification to fail. A signature scheme that
never fails is a checksum with extra steps.

Nothing here reaches the OpenSandbox. The generators render inside a container,
which is unavailable on this host, so these tests exercise the signing layer
directly and through ``ArtifactService`` with the sandbox render stubbed — the
same seam ``ArtifactService`` uses for every artifact, since it signs the bytes
that land on disk regardless of which renderer produced them.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from backend.deliverables.service import (
    SIGNATURE_FAILED,
    SIGNED,
    UNSIGNED,
    ArtifactService,
)
from backend.security.signing import (
    ALGORITHM,
    DEFAULT_KEY_FILE,
    KeyConfigurationError,
    SignedArtifact,
    default_key_path,
    generate_key,
    load_or_create_key,
    sign_file,
    signature_path_for,
    verify_file,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def key(tmp_path):
    return generate_key(tmp_path / "signing.pem")


@pytest.fixture
def artifact(tmp_path):
    path = tmp_path / "report.pdf"
    path.write_bytes(b"%PDF-1.4\nthis is the artifact body\n%%EOF\n")
    return path


def _flip_one_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[10] ^= 0x01
    path.write_bytes(bytes(data))


# ============================================================ ACCEPTANCE =====


def test_sign_then_verify_is_valid(artifact, key):
    signed = sign_file(artifact, key=key)
    assert isinstance(signed, SignedArtifact)
    assert signed.signature_path.is_file()

    outcome = verify_file(artifact)

    assert outcome.status == "SIGNATURE VALID"
    assert outcome.valid is True
    assert outcome.signature_present is True
    assert outcome.key_id == key.key_id
    assert outcome.algorithm == ALGORITHM


def test_flipping_one_byte_makes_verification_fail(artifact, key):
    sign_file(artifact, key=key)
    assert verify_file(artifact).status == "SIGNATURE VALID"

    _flip_one_byte(artifact)

    outcome = verify_file(artifact)
    assert outcome.status == "SIGNATURE INVALID"
    assert outcome.valid is False
    assert outcome.digest != outcome.expected_digest
    assert "modified after it was signed" in outcome.detail


# ================================================================== keys =====


def test_key_is_generated_on_first_use_with_0600(tmp_path, monkeypatch):
    target = tmp_path / "keys" / DEFAULT_KEY_FILE
    monkeypatch.setenv("P117_ARTIFACT_SIGNING_KEY", str(target))

    assert not target.exists()
    first = load_or_create_key()
    assert target.is_file()

    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600, f"private key mode is {oct(mode)}, not 0600"

    # ...and it is reused, not regenerated (or every restart would orphan the
    # signatures written before it).
    second = load_or_create_key()
    assert second.key_id == first.key_id


def test_env_var_overrides_the_key_path(tmp_path, monkeypatch):
    target = tmp_path / "custom.pem"
    monkeypatch.setenv("P117_ARTIFACT_SIGNING_KEY", str(target))
    assert default_key_path() == target
    generate_key()
    assert target.is_file()


def test_key_dir_env_moves_the_default(tmp_path, monkeypatch):
    monkeypatch.delenv("P117_ARTIFACT_SIGNING_KEY", raising=False)
    monkeypatch.setenv("P117_ARTIFACT_SIGNING_KEY_DIR", str(tmp_path / "vault"))
    assert default_key_path() == tmp_path / "vault" / DEFAULT_KEY_FILE


def test_a_garbage_key_file_is_rejected_not_ignored(tmp_path):
    target = tmp_path / "bad.pem"
    target.write_text("this is not a private key")
    with pytest.raises(KeyConfigurationError):
        load_or_create_key(target)


def test_two_keys_produce_different_signatures(artifact, tmp_path):
    key_a = generate_key(tmp_path / "a.pem")
    key_b = generate_key(tmp_path / "b.pem")
    sign_file(artifact, key=key_a)
    outcome = verify_file(artifact)
    assert outcome.key_id == key_a.key_id
    assert outcome.key_id != key_b.key_id
    assert verify_file(artifact).status == "SIGNATURE VALID"


# ============================================== the sidecar is the proof ====


def test_substituting_a_signature_from_another_file_is_detected(tmp_path, key):
    """A valid signature must not be replayable onto a different artifact."""
    original = tmp_path / "one.pdf"
    original.write_bytes(b"the original, signed document")
    other = tmp_path / "two.pdf"
    other.write_bytes(b"a completely different document")

    signed = sign_file(original, key=key)
    # Copy one.pdf's signature over two.pdf's sidecar.
    signature_path_for(other).write_bytes(signed.signature_path.read_bytes())

    outcome = verify_file(other)
    assert outcome.status == "SIGNATURE INVALID"


def test_truncation_is_detected(artifact, key):
    sign_file(artifact, key=key)
    artifact.write_bytes(artifact.read_bytes()[:5])
    outcome = verify_file(artifact)
    assert outcome.status == "SIGNATURE INVALID"


def test_tampering_with_the_recorded_digest_inside_the_sidecar_is_detected(artifact, key):
    signed = sign_file(artifact, key=key)
    sidecar = json.loads(signed.signature_path.read_text())
    sidecar["sha256"] = "0" * 64
    signed.signature_path.write_text(json.dumps(sidecar))
    outcome = verify_file(artifact)
    assert outcome.status == "SIGNATURE INVALID"


def test_unknown_algorithm_is_refused(artifact, key):
    signed = sign_file(artifact, key=key)
    sidecar = json.loads(signed.signature_path.read_text())
    sidecar["algorithm"] = "RSASSA-PKCS1-v1_5"
    signed.signature_path.write_text(json.dumps(sidecar))
    outcome = verify_file(artifact)
    assert outcome.status == "SIGNATURE INVALID"
    assert "only accepts" in outcome.detail


def test_a_corrupt_sidecar_is_invalid_not_a_crash(artifact, key):
    sign_file(artifact, key=key)
    signature_path_for(artifact).write_text("{not json")
    outcome = verify_file(artifact)
    assert outcome.status == "SIGNATURE INVALID"
    assert "not readable JSON" in outcome.detail


# ============================================================== unsigned =====


def test_unsigned_file_says_unsigned(artifact):
    """No signature is reported as UNSIGNED — never as valid."""
    outcome = verify_file(artifact)
    assert outcome.status == "UNSIGNED"
    assert outcome.valid is False
    assert outcome.signature_present is False
    assert outcome.digest  # the digest is still measured and reported


def test_missing_file_is_unsigned_not_valid(tmp_path):
    outcome = verify_file(tmp_path / "does-not-exist.pdf")
    assert outcome.status == "UNSIGNED"
    assert outcome.valid is False


# ============================================================== the CLI ======


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "backend.security.verify_artifact", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_cli_reports_valid_then_invalid_after_a_byte_flip(tmp_path, monkeypatch):
    """The end-to-end utility, exactly as an operator runs it."""
    key_path = tmp_path / "cli.pem"
    monkeypatch.setenv("P117_ARTIFACT_SIGNING_KEY", str(key_path))

    artifact = tmp_path / "signed-report.docx"
    artifact.write_bytes(b"PK\x03\x04 pretend docx bytes")

    from backend.security.signing import sign_file as do_sign

    do_sign(artifact, key=generate_key(key_path))

    valid = _run_cli(str(artifact))
    assert valid.returncode == 0, valid.stderr
    assert "SIGNATURE VALID" in valid.stdout

    _flip_one_byte(artifact)

    invalid = _run_cli(str(artifact))
    assert invalid.returncode == 1, invalid.stderr
    assert "SIGNATURE INVALID" in invalid.stdout

    # ...and an unsigned file is its own outcome, with its own exit code.
    unsigned_file = tmp_path / "never-signed.pdf"
    unsigned_file.write_bytes(b"%PDF-1.4")
    unsigned = _run_cli(str(unsigned_file))
    assert unsigned.returncode == 2
    assert "UNSIGNED" in unsigned.stdout


def test_cli_json_output(tmp_path, key, monkeypatch):
    monkeypatch.setenv("P117_ARTIFACT_SIGNING_KEY", str(tmp_path / "k.pem"))
    artifact = tmp_path / "a.pdf"
    artifact.write_bytes(b"body")
    sign_file(artifact, key=key)
    result = _run_cli(str(artifact), "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "SIGNATURE VALID"
    assert payload["algorithm"] == ALGORITHM


def test_shell_wrapper_exists_and_is_executable():
    wrapper = REPO_ROOT / "scripts" / "verify_artifact"
    assert wrapper.is_file()
    assert os.access(wrapper, os.X_OK)


# ====================================================== the service path =====


class _StubSandbox:
    """Stands in for the OpenSandbox renderer, which is not running here."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls = 0

    async def render_artifact(self, *, artifact_type, spec, filename, job_id=None, **kw):
        import hashlib

        self.calls += 1
        return {
            "ok": True,
            "bytes": self.payload,
            "sha256": hashlib.sha256(self.payload).hexdigest(),
            "size_bytes": len(self.payload),
            "filename": filename,
            "execution": {"execution_id": "stub-exec"},
        }


@pytest.fixture
def session_factory(tmp_path):
    """A real SQLite artifact store (the service only reads rows back from it)."""
    from backend.database.base import (
        create_engine_for,
        create_session_factory,
        init_db,
    )

    engine = create_engine_for(f"sqlite:///{tmp_path / 'artifacts.db'}")
    init_db(engine)
    return create_session_factory(engine)


SPEC = {
    "type": "docx",
    "title": "Signed report",
    "sections": [
        {
            "heading": "Findings",
            "paragraphs": ["pump P-101 vibration rose"],
        }
    ],
}


@pytest.mark.asyncio
async def test_service_signs_a_generated_artifact(tmp_path, key, session_factory):
    service = ArtifactService(
        sandbox=_StubSandbox(b"PK\x03\x04 rendered docx"),
        storage_dir=tmp_path / "out",
        session_factory=session_factory,
        signing_key=key,
    )
    record = await service.generate(spec=SPEC, artifact_type="docx", user="tester")

    assert record["signature_status"] == SIGNED
    assert record["signature_key_id"] == key.key_id
    assert record["signature_path"]

    # The sidecar is beside the file, and the file verifies.
    stored = Path(record["storage_path"])
    assert signature_path_for(stored).is_file()
    assert verify_file(stored).status == "SIGNATURE VALID"

    # The row records how it was signed, and the API-facing verifier agrees.
    persisted = service.get(record["artifact_id"])
    assert persisted["signature_status"] == SIGNED
    assert service.verify_signature(record["artifact_id"])["status"] == "SIGNATURE VALID"

    # Tamper with the stored artifact: the service's own verifier must fail.
    _flip_one_byte(stored)
    outcome = service.verify_signature(record["artifact_id"])
    assert outcome["status"] == "SIGNATURE INVALID"


@pytest.mark.asyncio
async def test_service_without_a_key_marks_the_artifact_unsigned(tmp_path, session_factory):
    service = ArtifactService(
        sandbox=_StubSandbox(b"bytes"),
        storage_dir=tmp_path / "out",
        session_factory=session_factory,
    )
    record = await service.generate(spec=SPEC, artifact_type="docx", user="tester")
    assert record["signature_status"] == UNSIGNED
    assert record["signature_path"] is None

    # ...and the summary reports it as unsigned rather than as fine.
    summary = service.signed_artifacts()
    assert summary["totals"]["unsigned"] == 1
    assert summary["totals"]["signed"] == 0
    assert summary["flagged"] is True  # no key configured


@pytest.mark.asyncio
async def test_service_records_signing_failure_instead_of_pretending(
    tmp_path, key, session_factory
):
    """A signing error must be visible on the record, not silently dropped."""
    service = ArtifactService(
        sandbox=_StubSandbox(b"bytes"),
        storage_dir=tmp_path / "out",
        session_factory=session_factory,
        signing_key=key,
    )

    def _explode(*args, **kwargs):
        raise RuntimeError("key store unavailable")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("backend.security.signing.sign_file", _explode)
    try:
        record = await service.generate(spec=SPEC, artifact_type="docx", user="tester")
    finally:
        monkeypatch.undo()

    assert record["signature_status"] == SIGNATURE_FAILED
    assert "key store unavailable" in record["signature_error"]
    # The artifact itself is not lost, and the row says what happened.
    assert Path(record["storage_path"]).is_file()
    assert service.signed_artifacts()["totals"]["signature_failed"] == 1


@pytest.mark.asyncio
async def test_signed_artifacts_summary_is_real(tmp_path, key):
    service = ArtifactService(
        sandbox=_StubSandbox(b"payload"), storage_dir=tmp_path / "out", signing_key=key
    )
    summary = service.signed_artifacts()
    # No artifact store wired -> an honest "unavailable", not an empty pass.
    assert summary["available"] is False
    assert summary["artifacts"] == []


def test_signed_artifacts_endpoint_reports_real_rows(tmp_path, key):
    """The endpoint the Sovereignty Center reads, over a real SQLite artifact."""
    from backend.api.src.main import create_app
    from backend.config import Settings
    from fastapi.testclient import TestClient

    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'a.db'}",
        uploads_dir=tmp_path / "uploads",
        artifacts_dir=tmp_path / "artifacts",
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as client:
        body = client.get("/api/artifacts/signatures").json()
        # The route resolves (not swallowed by /{artifact_id}) and reports real
        # state: nothing generated yet means zero signed artifacts.
        assert body["available"] is True
        assert body["algorithm"] == ALGORITHM
        assert body["totals"]["signed"] == 0
        assert body["artifacts"] == []
        assert isinstance(body["key_id"], str) and body["key_id"]

        # A known artifact id that does not exist is a 404, not a crash.
        assert client.get("/api/artifacts/nope/signature").status_code == 404
