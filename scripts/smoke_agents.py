"""Runtime smoke test for Phase 7 agents + the task decomposer.

Runs with pydantic only (no fastapi/sqlalchemy needed), by loading the modules
by file path into synthetic package entries. Exercises the paths that matter:
refusal without evidence, the artifact-spec validation/repair loop, code
extraction, and deterministic decomposition.
"""

import asyncio
import importlib.util
import sys
import traceback
import types
from pathlib import Path
from typing import Any

# Repository root, derived from this file's location. The previous value was
# the absolute path "/data/sih_extract/SIH/backend", which exists only on the
# machine this was first written on, so the script could not run from a clone.
ROOT = str(Path(__file__).resolve().parents[1])

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


def info(label: str, value: Any) -> None:
    print(f"  info  {label}: {value}")


def fake_package(name: str, path: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    module.__path__ = [path]  # type: ignore[attr-defined]
    sys.modules[name] = module
    return module


def load(name: str, relpath: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, f"{ROOT}/{relpath}")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --- fakes -----------------------------------------------------------------


class FakeReply:
    def __init__(self, content: str, model: str) -> None:
        self.content = content
        self.model = model
        self.usage = {"total_tokens": 42}


class FakeProvider:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[Any] = []

    async def chat(self, *, model, messages, temperature=0.2, max_tokens=None):
        self.calls.append(messages)
        content = self.replies.pop(0) if self.replies else ""
        return FakeReply(content, model)


class FakeResolved:
    def __init__(self, provider: FakeProvider) -> None:
        self.provider = provider
        self.model = "qwen-local:test"
        self.provider_name = "fake"


class FakeRouter:
    def __init__(self, provider: FakeProvider) -> None:
        self.provider = provider
        self.roles: list[str] = []

    async def resolve(self, role, *, model_override=None):
        self.roles.append(role)
        return FakeResolved(self.provider)


class DeadRouter:
    async def resolve(self, role, *, model_override=None):
        raise RuntimeError("no model is configured for role 'reasoning'")


class FakeContext:
    def __init__(self, count: int = 2) -> None:
        self.evidence = list(range(count))
        self.has_evidence = count > 0

    def prompt_text(self) -> str:
        return (
            "[1] pump-manual.pdf - page 12 - 5.2 Overhaul (document_id=doc1, chunk_id=doc1_7)\n"
            "The overhaul interval is 8000 running hours."
        )


VALID_SPEC = (
    '{"type": "pptx", "title": "Pump P-101 overhaul", '
    '"slides": [{"title": "Scope", "layout": "title_content", '
    '"bullets": [{"text": "Overhaul interval is 8000 running hours.", '
    '"citations": [{"document_id": "doc1", "page": 12, "section": "5.2", '
    '"chunk_id": "doc1_7"}]}], "notes": ""}], '
    '"sources": [{"document_id": "doc1", "page": 12, "section": "5.2"}]}'
)
EMPTY_SPEC = '{"type": "pptx", "title": "Nothing", "slides": []}'


# --- 1. agents -------------------------------------------------------------

print("\n[1] Phase 7 agents")
try:
    fake_package("backend", f"{ROOT}/backend")
    fake_package("backend.models", f"{ROOT}/backend/models")
    fake_package("backend.models.providers", f"{ROOT}/backend/models/providers")
    fake_package("backend.deliverables", f"{ROOT}/backend/deliverables")
    fake_package("backend.agents", f"{ROOT}/backend/agents")
    for pkg in ("documentation", "maintenance", "operations", "data_analysis", "safety"):
        fake_package(f"backend.agents.{pkg}", f"{ROOT}/backend/agents/{pkg}")

    load("backend.models.providers.base", "backend/models/providers/base.py")
    load("backend.deliverables.spec", "backend/deliverables/spec.py")
    abase = load("backend.agents.base", "backend/agents/base/agent.py")
    maint = load("backend.agents.maintenance.agent", "backend/agents/maintenance/agent.py")
    safety = load("backend.agents.safety.agent", "backend/agents/safety/agent.py")
    ops = load("backend.agents.operations.agent", "backend/agents/operations/agent.py")
    da = load("backend.agents.data_analysis.agent", "backend/agents/data_analysis/agent.py")
    doc = load("backend.agents.documentation.agent", "backend/agents/documentation/agent.py")

    classes = [
        maint.MaintenanceAgent,
        ops.OperationsAgent,
        doc.DocumentationAgent,
        da.DataAnalysisAgent,
        safety.SafetyAgent,
    ]
    info("agents", [cls.name for cls in classes])
    check("five agents construct", len(classes) == 5)
    check(
        "every agent declares a role, never a model name",
        all(cls.model_role in ("reasoning", "coding", "vision", "domain") for cls in classes),
    )
    check(
        "specs serialise for GET /api/agents",
        all(isinstance(cls.spec().model_dump(), dict) for cls in classes),
    )
    check(
        "safety runs at temperature 0",
        safety.SafetyAgent.temperature == 0.0,
        str(safety.SafetyAgent.temperature),
    )

    # registry
    registry = abase.AgentRegistry()
    for cls in classes:
        registry.register_agent(cls)
    check("registry lists all five", len(registry.list()) == 5)
    built = registry.build("data-analysis", model_router=None, gateway=None, tools=None)
    check("registry builds by hyphenated name", built.name == "data-analysis")
    check(
        "registry accepts the underscored variant",
        registry.build("data_analysis").name == "data-analysis",
    )
    try:
        registry.build("nonexistent")
        check("unknown agent raises KeyError", False, "no error raised")
    except KeyError:
        check("unknown agent raises KeyError", True)

    async def main() -> None:
        # 1a. no evidence -> refuse WITHOUT calling the model
        provider = FakeProvider(["should never be used"])
        agent = maint.MaintenanceAgent(model_router=FakeRouter(provider))
        result = await agent.execute(task="why did the pump fail", context=FakeContext(0))
        check("ungrounded maintenance answer is refused", result.degraded is True)
        check("the refusal never reaches the model", provider.calls == [], str(len(provider.calls)))
        check("the refusal explains itself", "cannot answer" in result.answer.lower())

        # 1b. grounded answer
        provider = FakeProvider(["The interval is 8000 hours [1]."])
        router = FakeRouter(provider)
        agent = maint.MaintenanceAgent(model_router=router)
        result = await agent.execute(task="what is the overhaul interval", context=FakeContext())
        check("grounded answer is returned", "8000 hours" in result.answer)
        check("the model name is recorded", result.model == "qwen-local:test", str(result.model))
        check("a role was resolved, not a model", router.roles == ["reasoning"], str(router.roles))
        check("grounded is reported", result.grounded is True)
        check("evidence count is carried", result.evidence_count == 2)

        # 1c. missing citation markers are flagged
        provider = FakeProvider(["The interval is 8000 hours."])
        agent = ops.OperationsAgent(model_router=FakeRouter(provider))
        result = await agent.execute(task="how do I start the unit", context=FakeContext())
        check(
            "an uncited answer is noted for the citation checker",
            any("evidence markers" in note for note in result.notes),
            str(result.notes),
        )

        # 1d. safety refuses even when told to allow ungrounded answers
        provider = FakeProvider(["here is a procedure"])
        agent = safety.SafetyAgent(model_router=FakeRouter(provider))
        result = await agent.execute(
            task="what is the isolation procedure",
            context=FakeContext(0),
            arguments={"allow_ungrounded": True},
        )
        check("safety ignores allow_ungrounded", result.degraded is True)
        check("safety never reached the model", provider.calls == [])
        check(
            "safety attaches its standing note",
            any("controlled document" in note for note in result.notes),
            str(result.notes),
        )

        # 1e. an unreachable model is a configuration message, not a crash
        agent = maint.MaintenanceAgent(model_router=DeadRouter())
        result = await agent.execute(task="what is the interval", context=FakeContext())
        check("an unreachable model degrades instead of raising", result.degraded is True)
        check("the message names the cause", "could not be used" in result.answer)

        # 1f. data-analysis writes code instead of numbers
        code = "import json\nprint(json.dumps({'mtbf_hours': 512.0}))"
        provider = FakeProvider([f"I will resample by month [1].\n\n```python\n{code}\n```"])
        router = FakeRouter(provider)
        agent = da.DataAnalysisAgent(model_router=router)
        result = await agent.execute(
            task="compute MTBF", context=FakeContext(), arguments={"input_files": ["f.csv"]}
        )
        check("analysis code is extracted", result.code == code, str(result.code))
        check("the coding role is used", router.roles == ["coding"], str(router.roles))
        check("code is bridged in to_dict", result.to_dict().get("code") == code)

        provider = FakeProvider(["The MTBF is about 500 hours."])
        agent = da.DataAnalysisAgent(model_router=FakeRouter(provider))
        result = await agent.execute(task="compute MTBF", context=FakeContext())
        check("prose with no code block does not become code", result.code is None)
        check("no-code replies are degraded", result.degraded is True)
        check("to_dict omits an unset code key", "code" not in result.to_dict())

        # 1g. documentation authors a valid artifact spec
        provider = FakeProvider([VALID_SPEC])
        agent = doc.DocumentationAgent(model_router=FakeRouter(provider))
        result = await agent.execute(
            task="make a deck",
            context=FakeContext(),
            arguments={"artifact_type": "pptx", "requested_units": 1},
        )
        check("a valid spec is accepted", isinstance(result.spec, dict), str(result.spec)[:120])
        check("the spec keeps its type", (result.spec or {}).get("type") == "pptx")
        check("one model call was needed", len(provider.calls) == 1, str(len(provider.calls)))
        check("the agent does not invent a filename", result.filename is None)

        # 1h. invalid spec -> one repair round trip
        provider = FakeProvider([EMPTY_SPEC, VALID_SPEC])
        agent = doc.DocumentationAgent(model_router=FakeRouter(provider))
        result = await agent.execute(
            task="make a deck", context=FakeContext(), arguments={"artifact_type": "pptx"}
        )
        check("an invalid spec is repaired once", isinstance(result.spec, dict))
        check("the repair used exactly one extra call", len(provider.calls) == 2)

        # 1i. two invalid specs -> refuse, and emit no spec at all
        provider = FakeProvider([EMPTY_SPEC, "still not json"])
        agent = doc.DocumentationAgent(model_router=FakeRouter(provider))
        result = await agent.execute(
            task="make a deck", context=FakeContext(), arguments={"artifact_type": "pptx"}
        )
        check("a twice-invalid spec is refused", result.spec is None)
        check("the failure is degraded and explained", result.degraded is True)
        check("no spec key is bridged to the generator", "spec" not in result.to_dict())
        info("spec failure note", result.notes[-1][:120] if result.notes else None)

        # 1j. a bullet with no citation is reported
        uncited = VALID_SPEC.replace(
            '"citations": [{"document_id": "doc1", "page": 12, "section": "5.2", '
            '"chunk_id": "doc1_7"}]',
            '"citations": []',
        )
        provider = FakeProvider([uncited])
        agent = doc.DocumentationAgent(model_router=FakeRouter(provider))
        result = await agent.execute(
            task="make a deck", context=FakeContext(), arguments={"artifact_type": "pptx"}
        )
        check(
            "uncited bullets are counted",
            any("carry no citation" in note for note in result.notes),
            str(result.notes),
        )

    asyncio.run(main())
except Exception:
    FAIL += 1
    print("  FAIL  agents could not be exercised")
    traceback.print_exc()


# --- 2. task decomposer ----------------------------------------------------

print("\n[2] task decomposer")
try:
    fake_package("backend.orchestrator", f"{ROOT}/backend/orchestrator")
    td = load(
        "backend.orchestrator.src.task_decomposer",
        "backend/orchestrator/src/task_decomposer.py",
    )

    single = td.decompose("What is the overhaul interval for pump P-101?")
    check("a single ask stays single", single.origin == "single", single.origin)
    check("a single ask has one subtask", len(single.subtasks) == 1)

    compound = td.decompose(
        "Read this maintenance manual and list the recommended overhaul intervals, "
        "then build me a ten-slide deck citing the source pages."
    )
    info("subtasks", [item.text[:48] for item in compound.subtasks])
    check("a compound ask is split", compound.is_compound is True)
    check("the deliverable is detected", compound.expects_artifact is True)
    check(
        "the artifact subtask is the dependent one",
        bool(compound.subtasks[-1].depends_on),
        str(compound.subtasks[-1].to_dict()),
    )
    check("ordering is reported", compound.sequential() is True)

    decimals = td.decompose("Vibration reached 7.1 mm/s at 1.5x speed. Create a report.")
    check("decimals do not split a sentence", len(decimals.subtasks) == 2, str(len(decimals.subtasks)))
    check(
        "the measurement survives intact",
        any("7.1 mm/s" in item.text for item in decimals.subtasks),
        str([item.text for item in decimals.subtasks]),
    )

    enumerated = td.decompose(
        "1. read the inspection report 2. list every recorded defect "
        "3. estimate the remaining life 4. draft the findings section "
        "5. build a summary deck 6. list open questions 7. propose an inspection interval"
    )
    check(
        "more asks than the cap are merged, never dropped",
        len(enumerated.subtasks) == td.MAX_SUBTASKS,
        str(len(enumerated.subtasks)),
    )
    check("the merge is disclosed", bool(enumerated.notes), str(enumerated.notes))
    check(
        "the last ask still appears",
        "inspection interval" in enumerated.subtasks[-1].text,
        enumerated.subtasks[-1].text[:80],
    )

    trailing = td.decompose("Summarise section 7 and cite it")
    check(
        "a short modifier is folded in, not promoted",
        len(trailing.subtasks) == 1,
        str([item.text for item in trailing.subtasks]),
    )

    empty = td.decompose("   ")
    check("an empty task is reported, not guessed", empty.subtasks == [] and bool(empty.notes))
    check("summary carries counts only", set(compound.summary()) >= {"subtasks", "compound"})
except Exception:
    FAIL += 1
    print("  FAIL  decomposer could not be exercised")
    traceback.print_exc()


print(f"\n==== {PASS} passed, {FAIL} failed ====")
sys.exit(1 if FAIL else 0)
