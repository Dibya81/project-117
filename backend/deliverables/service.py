"""Artifact lifecycle (Phase 10).

Implements the flow the review asked for, end to end and in this order::

    LLM -> structured artifact specification -> tool -> sandbox -> artifact
        -> SHA-256 -> verification -> store -> return

The ordering is the design. Each arrow removes a category of failure:

* **spec before code.** The model produces a validated ``ArtifactSpec``, never
  python-pptx calls. An invalid spec fails here, cheaply, with a message about
  the spec - not as a traceback from inside a container.
* **sandbox before bytes.** Rendering happens in the locked-down documents
  image. The API process never imports python-pptx, so a malformed spec cannot
  crash or exploit a parser inside the service.
* **digest before storage.** The SHA-256 is taken on the bytes as they leave
  the sandbox, then re-derived after the file lands on disk and the two are
  compared. A mismatch means the artifact changed in transit or on write, and
  is refused. Storing first and hashing later would hash whatever was written,
  which proves nothing.
* **verification before "done".** The row is created with
  ``verification_status='pending'``. It becomes ``passed``/``warning`` only
  when a checker has actually opened the file. Nothing in this service can set
  it to passed on its own.

What is deliberately *not* here: any path that returns an artifact whose
verification failed without saying so. ``record_for_download`` refuses a
failed artifact unless the caller passes ``acknowledge_unverified=True``, which
the API turns into an explicit user action.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.deliverables.spec import ArtifactSpec, SpecError, parse_spec

logger = logging.getLogger(__name__)

_EXTENSIONS = {"pptx": ".pptx", "docx": ".docx", "xlsx": ".xlsx", "pdf": ".pdf"}

#: Verification statuses stored on the artifact row.
STATUS_PENDING = "pending"
STATUS_PASSED = "verified"
STATUS_WARNING = "verified_with_warnings"
STATUS_FAILED = "rejected"
STATUS_UNVERIFIED = "unverified"

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class ArtifactError(RuntimeError):
    reason = "artifact_generation_failed"


class ArtifactSpecInvalid(ArtifactError):
    reason = "artifact_spec_invalid"


class ArtifactIntegrityError(ArtifactError):
    reason = "artifact_integrity_failed"


class ArtifactNotFound(KeyError):
    reason = "artifact_not_found"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def safe_filename(title: str, artifact_type: str) -> str:
    """Derive a filename from the spec title.

    The title is model output, so it is slugified rather than trusted: no
    directory separators, no leading dots, length-capped. The extension comes
    from the artifact type, never from the title.
    """
    stem = _SAFE_NAME.sub("-", (title or "artifact").strip()).strip("-._")
    stem = (stem or "artifact")[:80]
    return f"{stem}{_EXTENSIONS.get(artifact_type, '.bin')}"


class ArtifactService:
    def __init__(
        self,
        *,
        sandbox: Any,
        storage_dir: str | Path,
        session_factory: Any = None,
        audit: Any = None,
        verifier: Any = None,
    ) -> None:
        self._sandbox = sandbox
        self._dir = Path(storage_dir)
        self._sessions = session_factory
        self._audit = audit
        self._verifier = verifier

    @property
    def storage_dir(self) -> Path:
        return self._dir

    def supported_types(self) -> list[str]:
        return sorted(_EXTENSIONS)

    # --- generation -------------------------------------------------------

    async def generate(
        self,
        *,
        spec: dict[str, Any],
        artifact_type: str,
        job_id: str | None = None,
        user: str | None = None,
        filename: str | None = None,
        verify: bool = True,
    ) -> dict[str, Any]:
        artifact_type = (artifact_type or "").lower().strip()
        if artifact_type not in _EXTENSIONS:
            raise ArtifactSpecInvalid(
                f"unsupported artifact type '{artifact_type}'; "
                f"supported: {', '.join(sorted(_EXTENSIONS))}"
            )
        if self._sandbox is None:
            raise ArtifactError(
                "artifact generation requires the sandbox; document libraries are "
                "deliberately not installed in the API process"
            )

        try:
            validated: ArtifactSpec = parse_spec(spec, expected_type=artifact_type)
        except SpecError as exc:
            # A bad spec is a planning error, not a rendering error. Say so,
            # so the recovery manager replans instead of retrying identically.
            raise ArtifactSpecInvalid(str(exc)) from exc

        target_name = filename or safe_filename(validated.title, artifact_type)
        payload = validated.model_dump(mode="json")

        result = await self._sandbox.render_artifact(
            artifact_type=artifact_type,
            spec=payload,
            filename=target_name,
            job_id=job_id,
        )
        execution = result.get("execution") or {}
        if not result.get("ok"):
            self._record_audit(
                action="artifact.generate",
                artifact_id=None,
                user=user,
                outcome="failure",
                job_id=job_id,
                error=(result.get("error") or "generator failed")[:500],
                detail={"type": artifact_type, "execution": execution.get("execution_id")},
            )
            raise ArtifactError(
                f"the {artifact_type} generator failed: "
                f"{(result.get('error') or execution.get('stderr') or 'no output')[:400]}"
            )

        data: bytes = result["bytes"]
        sandbox_digest: str = result["sha256"]
        artifact_id = f"art_{uuid.uuid4().hex[:16]}"
        stored_name = f"{artifact_id}{_EXTENSIONS[artifact_type]}"
        path = self._dir / stored_name

        on_disk_digest = await asyncio.to_thread(self._write, path, data)
        if on_disk_digest != sandbox_digest:
            # Refuse rather than record a digest we know is wrong.
            await asyncio.to_thread(self._unlink, path)
            raise ArtifactIntegrityError(
                "the artifact digest changed between the sandbox and disk; the file "
                "was discarded"
            )

        record = {
            "artifact_id": artifact_id,
            "job_id": job_id,
            "type": artifact_type,
            "filename": result.get("filename") or target_name,
            "storage_path": str(path),
            "size_bytes": len(data),
            "sha256": sandbox_digest,
            "sandbox_execution_id": execution.get("execution_id"),
            "verification_status": STATUS_PENDING,
            "created_by": user,
            "created_at": _utcnow().isoformat(),
            "spec": {
                "type": artifact_type,
                "title": validated.title,
                "content_units": validated.content_units(),
                "citations": len(validated.all_citations()),
            },
        }
        await asyncio.to_thread(self._persist, record, payload)

        self._record_audit(
            action="artifact.generate",
            artifact_id=artifact_id,
            user=user,
            outcome="success",
            job_id=job_id,
            detail={
                "type": artifact_type,
                "size_bytes": len(data),
                "sha256": sandbox_digest[:16],
                "content_units": validated.content_units(),
            },
        )

        if verify and self._verifier is not None:
            report = await self._verify_one(record)
            record["verification_status"] = report["status"]
            record["verification"] = report
            await asyncio.to_thread(
                self._update_verification, artifact_id, report["status"], report
            )
        elif verify:
            record["verification_status"] = STATUS_UNVERIFIED
            record["verification"] = {
                "status": STATUS_UNVERIFIED,
                "reason": "no verifier is wired; the file was never opened by a checker",
            }
            await asyncio.to_thread(
                self._update_verification,
                artifact_id,
                STATUS_UNVERIFIED,
                record["verification"],
            )

        return record

    # --- verification -----------------------------------------------------

    async def _verify_one(self, record: dict[str, Any]) -> dict[str, Any]:
        from backend.verification.base import VerificationInput

        payload = VerificationInput(
            task=f"verify {record['type']} artifact",
            answer="",
            evidence=[],
            artifacts=[record],
            sandbox=self._sandbox,
            job_id=record.get("job_id"),
            user=record.get("created_by"),
        )
        report = await self._verifier.verify(payload)
        summary = report.summary()
        # VerificationReport.status already speaks the vocabulary stored on the
        # artifact row. The mapping is kept explicit, and anything unrecognised
        # degrades to 'unverified' rather than to 'verified': an unknown status
        # is not evidence that a file was checked.
        mapping = {
            STATUS_PASSED: STATUS_PASSED,
            STATUS_WARNING: STATUS_WARNING,
            STATUS_FAILED: STATUS_FAILED,
            STATUS_UNVERIFIED: STATUS_UNVERIFIED,
        }
        summary["status"] = mapping.get(summary.get("status", ""), STATUS_UNVERIFIED)
        return summary

    def mark_verification(self, artifact_id: str, *, status: str, report: dict[str, Any]) -> None:
        """Record the job-level verification outcome against the artifact."""
        self._update_verification(artifact_id, status, report)

    # --- retrieval --------------------------------------------------------

    def get(self, artifact_id: str) -> dict[str, Any]:
        row = self._load(artifact_id)
        if row is None:
            raise ArtifactNotFound(f"artifact '{artifact_id}' is not recorded")
        return row

    def list(self, *, job_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if self._sessions is None:
            return []
        from backend.database.execution import Artifact

        with self._sessions() as session:
            query = session.query(Artifact).order_by(Artifact.created_at.desc())
            if job_id:
                query = query.filter(Artifact.job_id == job_id)
            return [self._to_dict(row) for row in query.limit(max(1, min(limit, 200))).all()]

    def open_for_download(
        self,
        artifact_id: str,
        *,
        acknowledge_unverified: bool = False,
    ) -> dict[str, Any]:
        """Resolve an artifact for download, re-checking integrity first.

        Two refusals live here rather than in the API layer, so every caller
        inherits them:

        * a digest that no longer matches means the stored file changed after
          generation - it is never served;
        * a ``failed`` or ``unverified`` artifact requires the caller to say
          out loud that it is taking an unverified file.
        """
        record = self.get(artifact_id)
        path = Path(record["storage_path"])
        if not path.is_file():
            raise ArtifactNotFound(f"the stored file for '{artifact_id}' is missing")

        digest = self._digest(path)
        if record.get("sha256") and digest != record["sha256"]:
            raise ArtifactIntegrityError(
                f"artifact '{artifact_id}' no longer matches its recorded digest and "
                "will not be served"
            )

        status = record.get("verification_status")
        if status in {STATUS_FAILED, STATUS_UNVERIFIED, STATUS_PENDING} and not acknowledge_unverified:
            raise ArtifactError(
                f"artifact '{artifact_id}' has verification status '{status}'; "
                "re-request with an explicit unverified acknowledgement to download it"
            )
        record["acknowledged_unverified"] = bool(
            acknowledge_unverified and status != STATUS_PASSED
        )
        return record

    # --- storage / persistence -------------------------------------------

    def _write(self, path: Path, data: bytes) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".part")
        temporary.write_bytes(data)
        temporary.replace(path)
        return self._digest(path)

    def _unlink(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - best effort cleanup
            logger.warning("could not remove rejected artifact at %s", path)

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _persist(self, record: dict[str, Any], spec_payload: dict[str, Any]) -> None:
        if self._sessions is None:
            return
        from backend.database.execution import Artifact

        try:
            with self._sessions() as session:
                session.add(
                    Artifact(
                        id=record["artifact_id"],
                        job_id=record.get("job_id"),
                        type=record["type"],
                        filename=record["filename"],
                        storage_path=record["storage_path"],
                        size_bytes=record["size_bytes"],
                        sha256=record["sha256"],
                        sandbox_execution_id=record.get("sandbox_execution_id"),
                        verification_status=STATUS_PENDING,
                        spec_json=json.dumps(spec_payload)[:200_000],
                        created_by=record.get("created_by"),
                    )
                )
                session.commit()
        except Exception:
            # The file exists and its digest is known; losing the row must not
            # lose the artifact. Surfaced loudly in logs instead.
            logger.exception("failed to record artifact %s", record["artifact_id"])

    def _update_verification(
        self, artifact_id: str, status: str, report: dict[str, Any]
    ) -> None:
        if self._sessions is None:
            return
        from backend.database.execution import Artifact

        try:
            with self._sessions() as session:
                row = session.get(Artifact, artifact_id)
                if row is None:
                    return
                row.verification_status = status
                row.verification_json = json.dumps(report)[:200_000]
                session.commit()
        except Exception:
            logger.exception("failed to update verification for artifact %s", artifact_id)

    def _load(self, artifact_id: str) -> dict[str, Any] | None:
        if self._sessions is None:
            return None
        from backend.database.execution import Artifact

        with self._sessions() as session:
            row = session.get(Artifact, artifact_id)
            return self._to_dict(row) if row is not None else None

    @staticmethod
    def _to_dict(row: Any) -> dict[str, Any]:
        verification: dict[str, Any] = {}
        if row.verification_json:
            try:
                verification = json.loads(row.verification_json)
            except ValueError:  # pragma: no cover - defensive
                verification = {}
        return {
            "artifact_id": row.id,
            "job_id": row.job_id,
            "type": row.type,
            "filename": row.filename,
            "storage_path": row.storage_path,
            "size_bytes": row.size_bytes,
            "sha256": row.sha256,
            "sandbox_execution_id": row.sandbox_execution_id,
            "verification_status": row.verification_status,
            "verification": verification,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _record_audit(
        self,
        *,
        action: str,
        artifact_id: str | None,
        user: str | None,
        outcome: str,
        job_id: str | None,
        detail: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(
                action=action,
                resource_type="artifact",
                resource_id=artifact_id or (job_id or "-"),
                user=user,
                outcome=outcome,
                detail=detail or {},
                error=error,
            )
        except Exception:  # pragma: no cover - audit must never break the flow
            logger.warning("audit write failed for %s", action, exc_info=True)
