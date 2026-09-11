"""Runtime smoke checks that are possible in this sandbox.

Only pydantic is installed (no fastapi/sqlalchemy/httpx), so anything that
touches the database or HTTP layer cannot be imported here. What CAN be
executed is the pure logic: the verification checkers, the artifact spec
validator, and the tool specifications - including the security invariant
that no tool lets a model choose its own container image.

Modules that live under packages whose __init__ needs sqlalchemy are loaded
directly from file with a synthetic parent package, so the missing dependency
does not hide real logic errors.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import traceback
import types
from pathlib import Path

# Repository root, derived from this file's location. The previous value was
# the absolute path "/data/sih_extract/SIH/backend", which exists only on the
# machine this was first written on, so the script could not run from a clone.
ROOT = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, ROOT)

PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label} {detail}")


def info(label: str, value: object) -> None:
    print(f"  info  {label}: {value}")


def fake_package(name: str, path: str) -> None:
    module = types.ModuleType(name)
    module.__path__ = [path]  # type: ignore[attr-defined]
    sys.modules[name] = module


def load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, f"{ROOT}/{relpath}")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --- 1. artifact spec validation -------------------------------------------

print("\n[1] deliverables/spec.py")
try:
    fake_package("backend", f"{ROOT}/backend")
    fake_package("backend.deliverables", f"{ROOT}/backend/deliverables")
    spec_mod = load("backend.deliverables.spec", "backend/deliverables/spec.py")

    good = {
        "type": "pptx",
        "title": "Pump P-101 condition summary",
        "slides": [
            {
                "title": "Findings",
                "bullets": [
                    {
                        "text": "Vibration exceeded the alarm limit in March.",
                        "citations": [{"document_id": "doc-1", "page": 143, "section": "5.2"}],
                    }
                ],
            }
        ],
    }
    parsed = spec_mod.parse_spec(good, expected_type="pptx")
    check("a valid pptx spec parses", parsed.type == "pptx")
    check("content_units counts slides", parsed.content_units() == 1, parsed.content_units())
    check("all_citations finds the page", parsed.all_citations()[0].page == 143)

    for label, payload in [
        ("empty title rejected", {"type": "pptx", "title": "", "slides": good["slides"]}),
        ("pptx with no slides rejected", {"type": "pptx", "title": "T"}),
        (
            "docx content in a pptx rejected",
            {"type": "pptx", "title": "T", "sections": [{"heading": "H"}]},
        ),
        (
            "9 bullets on one slide rejected",
            {
                "type": "pptx",
                "title": "T",
                "slides": [
                    {"title": "S", "bullets": [{"text": f"b{i}"} for i in range(9)]}
                ],
            },
        ),
        ("unknown type rejected", {"type": "exe", "title": "T"}),
    ]:
        try:
            spec_mod.parse_spec(payload)
            check(label, False, "accepted an invalid spec")
        except spec_mod.SpecError:
            check(label, True)

    mismatch = {
        "type": "xlsx",
        "title": "T",
        "sheets": [{"name": "S", "columns": ["a", "b"], "rows": [["1"]]}],
    }
    try:
        spec_mod.parse_spec(mismatch)
        check("row shorter than columns rejected", False, "accepted a ragged row")
    except spec_mod.SpecError:
        check("row shorter than columns rejected", True)
except Exception:
    FAIL += 1
    print("  FAIL  spec module could not be exercised")
    traceback.print_exc()


# --- 2. verification checkers ----------------------------------------------

print("\n[2] verification checkers")
try:
    fake_package("backend.verification", f"{ROOT}/backend/verification")
    vbase = load("backend.verification.base", "backend/verification/base.py")
    ev_mod = load("backend.verification.evidence_checker", "backend/verification/evidence_checker.py")
    cite_mod = load("backend.verification.citation_checker", "backend/verification/citation_checker.py")
    calc_mod = load(
        "backend.verification.calculation_checker", "backend/verification/calculation_checker.py"
    )
    hall_mod = load(
        "backend.verification.hallucination_checker",
        "backend/verification/hallucination_checker.py",
    )
    pol_mod = load("backend.verification.policy_checker", "backend/verification/policy_checker.py")
    art_mod = load("backend.verification.artifact_checker", "backend/verification/artifact_checker.py")
    ver_mod = load("backend.verification.verifier", "backend/verification/verifier.py")

    VerificationInput = vbase.VerificationInput
    CheckStatus = vbase.CheckStatus

    evidence = [
        {
            "chunk_id": "c1",
            "text": "Bearing vibration reached 7.1 mm/s in March, above the 4.5 mm/s limit.",
            "citation": {"document_id": "doc-1", "page": 12, "heading_path": "5.2 Vibration"},
        }
    ]

    async def main() -> None:
        # 2a. a fabricated standard number must fail
        result = await hall_mod.HallucinationChecker().check(
            VerificationInput(
                task="summarise",
                answer="The pump must comply with ISO 10816 as stated on page 12.",
                evidence=evidence,
            )
        )
        check(
            "fabricated standard number fails",
            result.status is CheckStatus.FAILED,
            f"got {result.status} {result.findings}",
        )
        kinds = {f.get("kind") for f in result.findings}
        info("hallucination findings", sorted(str(k) for k in kinds))

        # 2b. a page that was never retrieved must fail
        result = await cite_mod.CitationChecker().check(
            VerificationInput(
                answer="Vibration exceeded the limit (page 143).",
                evidence=evidence,
            )
        )
        check(
            "citation to an unretrieved page fails",
            result.status is CheckStatus.FAILED,
            f"got {result.status}",
        )
        check(
            "the finding names the fabricated page",
            any(
                f.get("type") == "page_not_retrieved" and f.get("page") == 143
                for f in result.findings
            ),
            str(result.findings),
        )

        # 2c. a grounded answer citing a retrieved page must not fail
        result = await cite_mod.CitationChecker().check(
            VerificationInput(
                answer="Vibration reached 7.1 mm/s (page 12).",
                evidence=evidence,
            )
        )
        check(
            "citation to a retrieved page does not fail",
            result.status is not CheckStatus.FAILED,
            f"got {result.status} {result.message}",
        )

        # 2d. a leaked credential must fail AND must not be echoed
        secret = "AKIAIOSFODNN7EXAMPLE"
        result = await pol_mod.PolicyChecker().check(
            VerificationInput(answer=f"Use access key {secret} to connect.", evidence=evidence)
        )
        check("leaked credential fails", result.status is CheckStatus.FAILED, f"got {result.status}")
        blob = json.dumps(result.to_dict())
        check("credential value is never echoed in the finding", secret not in blob)
        info("policy findings", [f.get("kind") for f in result.findings])

        # 2e. evidence checker on an ungrounded answer
        result = await ev_mod.EvidenceChecker().check(
            VerificationInput(answer="Replace the bearing next Tuesday.", evidence=[])
        )
        info("evidence checker with no evidence", f"{result.status} - {result.message}")
        check("no-evidence answer is not reported as passed", result.status is not CheckStatus.PASSED)

        # 2f. calculation checker without a sandbox must skip, never pass
        result = await calc_mod.CalculationChecker().check(
            VerificationInput(answer="12 + 30 = 45", evidence=evidence, sandbox=None)
        )
        info("calculation checker without sandbox", f"{result.status} - {result.message}")
        check(
            "calculation checker does not pass without a sandbox",
            result.status is not CheckStatus.PASSED,
        )

        # 2g. artifact checker on a missing file must fail
        result = await art_mod.ArtifactChecker().check(
            VerificationInput(
                answer="Deck created.",
                artifacts=[{"type": "pptx", "filename": "a.pptx", "storage_path": "/nope/a.pptx"}],
            )
        )
        check(
            "missing artifact file fails",
            result.status is CheckStatus.FAILED,
            f"got {result.status} {result.findings}",
        )

        # 2h. the verifier aggregates and never turns skipped into passed
        verifier = ver_mod.Verifier()
        info("default checkers", verifier.checker_names)
        report = await verifier.verify(
            VerificationInput(
                task="summarise",
                answer="Vibration reached 7.1 mm/s (page 12).",
                evidence=evidence,
            )
        )
        summary = report.summary()
        info(
            "report status",
            f"{summary['status']} may_complete={summary['may_complete']} "
            f"ran={summary['checks_ran']} {summary['counts']}",
        )
        check("report lists every checker", len(summary["checks"]) == len(verifier.checker_names))

        report = await verifier.verify(
            VerificationInput(answer="Comply with ISO 10816.", evidence=evidence)
        )
        check(
            "a blocking failure blocks completion",
            report.may_complete is False,
            f"got may_complete={report.may_complete}",
        )
        check("blocking_failures names the checker", len(report.blocking_failures) >= 1)
        check("a rejected report reads 'rejected'", report.status == "rejected", report.status)

        empty = ver_mod.Verifier(checkers=[])
        report = await empty.verify(VerificationInput(answer="anything"))
        check(
            "verifying with no checkers blocks rather than passes",
            report.may_complete is False,
            f"got may_complete={report.may_complete}",
        )

        # An all-skipped report must never read as verified.
        skipped_only = vbase.VerificationReport()
        skipped_only.add(
            vbase.CheckResult(
                checker="citations",
                status=CheckStatus.SKIPPED,
                message="nothing to check",
                blocking=False,
            )
        )
        check(
            "an all-skipped report reads 'unverified', not 'verified'",
            skipped_only.status == "unverified",
            skipped_only.status,
        )
        check("checks_ran counts only real verdicts", skipped_only.summary()["checks_ran"] == 0)

        # A template placeholder is documentation, not a leak.
        result = await pol_mod.PolicyChecker().check(
            VerificationInput(answer="Set password: <your-password> before starting.")
        )
        check(
            "a template placeholder is not reported as a leak",
            result.status is not CheckStatus.FAILED,
            f"got {result.status} {result.findings}",
        )

    asyncio.run(main())
except Exception:
    FAIL += 1
    print("  FAIL  verification could not be exercised")
    traceback.print_exc()


# --- 3. tool specifications and security invariants ------------------------

print("\n[3] tool specs + security invariants")
try:
    fake_package("backend.tools", f"{ROOT}/backend/tools")
    fake_package("backend.tools.builtin", f"{ROOT}/backend/tools/builtin")
    tbase = load("backend.tools.base", "backend/tools/base.py")
    docs_mod = load("backend.tools.builtin.documents", "backend/tools/builtin/documents.py")
    code_mod = load("backend.tools.builtin.code", "backend/tools/builtin/code.py")
    art_tools = load("backend.tools.builtin.artifacts", "backend/tools/builtin/artifacts.py")

    tools = [
        docs_mod.SearchDocumentsTool(),
        docs_mod.ReadDocumentTool(),
        docs_mod.ExtractTableTool(),
        code_mod.AnalyzeCsvTool(),
        code_mod.RunPythonTool(),
        art_tools.CreatePptxTool(),
        art_tools.CreateDocxTool(),
        art_tools.CreateXlsxTool(),
        art_tools.CreatePdfTool(),
    ]
    names = [t.spec.name for t in tools]
    info("tools", names)
    check("nine built-in tools construct", len(tools) == 9)
    check("names are unique", len(set(names)) == 9)

    banned = ("image", "docker", "network", "env", "privileged", "mount", "volume")
    offenders = []
    for tool in tools:
        properties = set((tool.spec.input_schema.get("properties") or {}).keys())
        for word in banned:
            if word in properties:
                offenders.append(f"{tool.spec.name}.{word}")
    check(
        "no tool lets the caller choose an image, network or env",
        not offenders,
        str(offenders),
    )

    by_name = {t.spec.name: t.spec for t in tools}
    check(
        "run_python is execute risk",
        by_name["run_python"].risk is tbase.RiskLevel.EXECUTE,
    )
    check("run_python is marked sandboxed", by_name["run_python"].sandboxed is True)
    check(
        "run_python requires approval by default",
        by_name["run_python"].public()["requires_approval_by_default"] is True,
    )
    check(
        "analyze_csv runs a fixed script and needs no approval",
        by_name["analyze_csv"].public()["requires_approval_by_default"] is False,
    )
    check(
        "artifact tools need no approval",
        all(
            by_name[f"create_{k}"].public()["requires_approval_by_default"] is False
            for k in ("pptx", "docx", "xlsx", "pdf")
        ),
    )
    check(
        "read tools carry read risk",
        all(
            by_name[n].risk is tbase.RiskLevel.READ
            for n in ("search_documents", "read_document", "extract_table")
        ),
    )
    check(
        "every tool publishes an input schema",
        all(t.spec.input_schema.get("properties") for t in tools),
    )
    check(
        "every spec serialises for the catalogue",
        all(isinstance(json.dumps(t.spec.public()), str) for t in tools),
    )

    # argument validation actually rejects bad input
    bad = [
        ("run_python rejects an unknown field", code_mod.RunPythonArguments, {"code": "x", "image": "alpine"}),
        ("run_python rejects a traversal input name", code_mod.RunPythonArguments, {"code": "x", "inputs": {"../etc/passwd": "y"}}),
        ("run_python rejects an over-long timeout", code_mod.RunPythonArguments, {"code": "x", "timeout_seconds": 4000}),
        ("search rejects top_k above the cap", docs_mod.SearchDocumentsArguments, {"query": "q", "top_k": 500}),
        ("search rejects an unknown mode", docs_mod.SearchDocumentsArguments, {"query": "q", "mode": "magic"}),
        ("search rejects an empty query", docs_mod.SearchDocumentsArguments, {"query": ""}),
    ]
    for label, model, payload in bad:
        try:
            model.model_validate(payload)
            check(label, False, "accepted invalid arguments")
        except Exception:
            check(label, True)

    ok = code_mod.RunPythonArguments.model_validate({"code": "print(1)", "inputs": {"data.csv": "a,b"}})
    check("valid run_python arguments accepted", ok.code == "print(1)")
    check("input files default to empty", code_mod.RunPythonArguments.model_validate({"code": "x"}).inputs == {})
except Exception:
    FAIL += 1
    print("  FAIL  tools could not be exercised")
    traceback.print_exc()


# --- 4. the orchestrator -> verification hand-off --------------------------

print("\n[4] verification manager (the orchestrator's call site)")
try:
    fake_package("backend.orchestrator", f"{ROOT}/backend/orchestrator")
    vm_mod = load(
        "backend.orchestrator.src.verification_manager",
        "backend/orchestrator/src/verification_manager.py",
    )

    class _Boom:
        async def verify(self, payload):
            raise RuntimeError("checker infrastructure is down")

    async def main4() -> None:
        # Exactly the keyword arguments orchestrator.py passes.
        manager = vm_mod.VerificationManager()
        report = await manager.verify(
            task="summarise the manual",
            answer="Some answer.",
            evidence=[],
            artifacts=[],
            job_id="job_1",
            user=None,
        )
        check("the orchestrator's keyword call signature matches", report is not None)
        check(
            "no verifier wired reads 'unverified'",
            report.status == "unverified",
            report.status,
        )
        allowed, reason = manager.may_complete(report)
        check("unverified does not block completion", allowed is True and reason is None)
        check("describe() reports verification disabled", manager.describe()["enabled"] is False)

        broken = vm_mod.VerificationManager(verifier=_Boom())
        report = await broken.verify(task="t", answer="a")
        check(
            "a crashing verifier is a failure, not a pass",
            report.status == "rejected",
            report.status,
        )
        allowed, reason = broken.may_complete(report)
        check("a crashing verifier blocks completion", allowed is False)
        check("the reason names the checker", bool(reason) and "verifier" in (reason or ""), reason)
        info("block reason", reason)

    asyncio.run(main4())
except Exception:
    FAIL += 1
    print("  FAIL  verification manager could not be exercised")
    traceback.print_exc()


print(f"\n==== {PASS} passed, {FAIL} failed ====")
sys.exit(1 if FAIL else 0)
