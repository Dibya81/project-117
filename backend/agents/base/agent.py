"""Agent contracts and registry (Phase 1 shape, Phase 7 implementation).

An agent here is a *specialisation*, not a subsystem. It owns a prompt, a set
of declared capabilities, and the post-processing of its own output. It does
not own a model client, a retriever, a vector store or a tool executor - those
arrive through the constructor from the orchestrator, which is the only reason
five agents do not become five parallel half-systems.

Concretely, an agent may not:

- construct an HTTP client or name a model (it asks for a *role*);
- call retrieval (it receives an already-assembled context pack);
- execute a tool itself (it emits what a tool step will consume, and the
  registry enforces permission, approval and limits on the way through);
- decide whether its own answer is acceptable (verification does that).

What an agent returns is an :class:`AgentResult`. The two interesting fields
are ``code`` and ``spec``: a data-analysis agent designs an analysis and a
documentation agent designs a deck, and the plan's following tool step picks
those up. That split - the model writes the *content*, a deterministic tool
writes the *file*, a sandbox runs the *code* - is the whole reason a local 9B
model can be trusted with a report at all.

``degraded`` is deliberately part of the contract. An agent that could not
reach a model, or that was asked for a grounded answer with no evidence,
returns a result that says so instead of an empty string that reads like a
model with nothing to say.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from backend.models.providers.base import ChatMessage

logger = logging.getLogger(__name__)

#: Ceiling on how much prompt text one agent turn may carry. The context
#: manager already budgets evidence; this is a second, blunter guard so a
#: pathological task string cannot push a local model past its window.
MAX_PROMPT_CHARS = 60_000


class AgentSpec(BaseModel):
    """The public description of an agent, served by ``GET /api/agents``."""

    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    requires_rag: bool = False
    tools: list[str] = Field(default_factory=list)


class AgentError(RuntimeError):
    reason = "agent_failed"


class AgentModelUnavailable(AgentError):
    """No local model could serve this agent's role.

    Separate from a generic failure because the fix is configuration, not a
    retry: retrying an unconfigured role produces the same error more slowly.
    """

    reason = "model_unavailable"


@dataclass
class AgentResult:
    answer: str = ""
    agent: str = ""
    model: str | None = None
    #: True when the answer was produced from retrieved evidence.
    grounded: bool = False
    #: True when the agent could not do its job properly and said so.
    degraded: bool = False
    evidence_count: int = 0
    #: Python for a following ``run_python`` step, when the agent designed one.
    code: str | None = None
    #: Artifact specification for a following ``create_*`` step.
    spec: dict[str, Any] | None = None
    filename: str | None = None
    #: Short operator-facing notes: what was missing, what was refused.
    notes: list[str] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """The shape the execution manager reads.

        ``code``, ``spec`` and ``filename`` are omitted when unset, because the
        executor bridges whichever of those keys it finds into the next tool
        step. Emitting ``"spec": None`` would hand a generator an explicit null
        and turn a missing design into a confusing validation error.
        """
        payload: dict[str, Any] = {
            "answer": self.answer,
            "agent": self.agent,
            "model": self.model,
            "grounded": self.grounded,
            "degraded": self.degraded,
            "evidence_count": self.evidence_count,
        }
        if self.code is not None:
            payload["code"] = self.code
        if self.spec is not None:
            payload["spec"] = self.spec
        if self.filename is not None:
            payload["filename"] = self.filename
        if self.notes:
            payload["notes"] = self.notes[:10]
        if self.usage:
            payload["usage"] = self.usage
        return payload


class BaseAgent:
    """Template for every specialised agent.

    Subclasses set the class attributes and override :meth:`build_prompt` and
    optionally :meth:`postprocess`. The execution path - validate, prompt,
    call the resolved model, post-process - is shared, so a new agent cannot
    accidentally skip the parts that keep answers grounded.
    """

    name: str = "agent"
    description: str = ""
    capabilities: tuple[str, ...] = ()
    requires_rag: bool = True
    tool_names: tuple[str, ...] = ()
    #: Model *role*, never a model name.
    model_role: str = "reasoning"
    temperature: float = 0.2
    system_prompt: str = ""

    def __init__(
        self,
        *,
        model_router: Any = None,
        gateway: Any = None,
        tools: Any = None,
    ) -> None:
        self._router = model_router
        self._gateway = gateway
        self._tools = tools

    # --- introspection ----------------------------------------------------

    @classmethod
    def spec(cls) -> AgentSpec:
        return AgentSpec(
            name=cls.name,
            description=cls.description,
            capabilities=list(cls.capabilities),
            requires_rag=cls.requires_rag,
            tools=list(cls.tool_names),
        )

    def get_tools(self) -> list[str]:
        """The declared tools that are actually registered in this deployment.

        An agent that claims a tool the registry does not have would produce a
        plan step that fails at dispatch, so the intersection is the honest
        answer.
        """
        declared = list(self.tool_names)
        if self._tools is None:
            return declared
        try:
            available = set(self._tools.names())
        except Exception:  # pragma: no cover - defensive
            return declared
        return [name for name in declared if name in available]

    def get_capabilities(self) -> list[str]:
        return list(self.capabilities)

    # --- validation -------------------------------------------------------

    def validate(self, *, task: str, context: Any = None) -> list[str]:
        """Pre-flight complaints. Empty list means "go ahead".

        Returned rather than raised: "no evidence was retrieved" should shape
        the answer and be visible to the caller, not abort the job.
        """
        problems: list[str] = []
        if not (task or "").strip():
            problems.append("no task was given")
        if self.requires_rag and not bool(getattr(context, "has_evidence", False)):
            problems.append(
                "no document evidence was retrieved, so this answer cannot be grounded"
            )
        return problems

    def plan(self, *, task: str, context: Any = None) -> list[dict[str, Any]]:
        """What this agent would do, for a planner that wants a hint.

        The default is a single reasoning step. Agents that need a tool after
        their reasoning (analysis, artifact generation) override this, and the
        planner remains free to ignore it - the plan is validated centrally
        either way.
        """
        return [{"kind": "agent", "name": self.name, "description": self.description}]

    # --- execution --------------------------------------------------------

    async def execute(
        self,
        *,
        task: str,
        context: Any = None,
        job_id: str | None = None,
        user: str | None = None,
        roles: tuple[str, ...] = (),
        arguments: dict[str, Any] | None = None,
    ) -> AgentResult:
        arguments = dict(arguments or {})
        problems = self.validate(task=task, context=context)
        evidence_count = len(getattr(context, "evidence", []) or [])
        grounded = bool(getattr(context, "has_evidence", False))

        if self.requires_rag and not grounded and not arguments.get("allow_ungrounded"):
            # Refusing here is the point. A maintenance answer invented from a
            # model's general knowledge is worse than no answer, because it is
            # indistinguishable from a sourced one.
            return AgentResult(
                answer=(
                    "I cannot answer this from the indexed documents: no relevant passages "
                    "were retrieved. Upload or re-index the source document, or narrow the "
                    "question to a document that is indexed."
                ),
                agent=self.name,
                grounded=False,
                degraded=True,
                evidence_count=0,
                notes=problems,
            )

        messages = self.build_prompt(task=task, context=context, arguments=arguments)
        try:
            reply, model_name, usage = await self._complete(messages)
        except AgentModelUnavailable as exc:
            return AgentResult(
                answer=str(exc),
                agent=self.name,
                grounded=grounded,
                degraded=True,
                evidence_count=evidence_count,
                notes=[*problems, "the configured local model could not be used"],
            )

        result = AgentResult(
            answer=reply.strip(),
            agent=self.name,
            model=model_name,
            grounded=grounded,
            degraded=bool(problems),
            evidence_count=evidence_count,
            notes=problems,
            usage=usage,
        )
        return await self.postprocess(
            result, task=task, context=context, arguments=arguments
        )

    def build_prompt(
        self,
        *,
        task: str,
        context: Any = None,
        arguments: dict[str, Any] | None = None,
    ) -> list[ChatMessage]:
        """Default prompt: system rules, evidence, then the request."""
        evidence_text = self.evidence_text(context)
        user = f"Evidence:\n{evidence_text}\n\nRequest: {task}"
        return [
            ChatMessage(role="system", content=self.system_prompt),
            ChatMessage(role="user", content=user[:MAX_PROMPT_CHARS]),
        ]

    async def postprocess(
        self,
        result: AgentResult,
        *,
        task: str,
        context: Any = None,
        arguments: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Hook for agents that emit code or an artifact spec."""
        return result

    # --- helpers ----------------------------------------------------------

    @staticmethod
    def evidence_text(context: Any) -> str:
        if context is not None and hasattr(context, "prompt_text"):
            return str(context.prompt_text())
        return "No evidence was retrieved from the indexed documents for this request."

    async def _complete(
        self,
        messages: list[ChatMessage],
        *,
        role: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, str | None, dict[str, int]]:
        if self._router is None:
            raise AgentModelUnavailable(
                "No model router is configured, so no local model could be used. "
                "Set the model roles in .env (see .env.example) and restart."
            )
        try:
            resolved = await self._router.resolve(role or self.model_role)
            reply = await resolved.provider.chat(
                model=resolved.model,
                messages=messages,
                temperature=self.temperature if temperature is None else temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            logger.warning("agent '%s' could not reach a local model", self.name, exc_info=True)
            raise AgentModelUnavailable(
                f"The local model for role '{role or self.model_role}' could not be used: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        return (
            str(getattr(reply, "content", "") or ""),
            getattr(reply, "model", None) or resolved.model,
            dict(getattr(reply, "usage", {}) or {}),
        )

    @staticmethod
    def extract_fenced(text: str, language: str = "python") -> str | None:
        """Pull a fenced code block out of a model reply.

        Local models fence inconsistently, so both ```python and bare ``` are
        accepted; anything else returns ``None`` rather than a guess, because
        guessing here means sending prose to an interpreter.
        """
        if not text:
            return None
        pattern = re.compile(
            rf"```(?:{language})?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE
        )
        match = pattern.search(text)
        if match and match.group(1).strip():
            return match.group(1).strip()
        return None


class AgentRegistry:
    """Holds agent descriptions and, from Phase 7, their implementations.

    ``register`` keeps working for a bare :class:`AgentSpec` so the Phase 1
    ``GET /api/agents`` behaviour is unchanged. ``register_agent`` adds a class
    that :meth:`build` can instantiate with injected dependencies - the hook
    :class:`~backend.orchestrator.src.agent_manager.AgentManager` looks for.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentSpec] = {}
        self._implementations: dict[str, type[BaseAgent]] = {}

    def register(self, spec: AgentSpec) -> None:
        self._agents[spec.name] = spec

    def register_agent(self, agent_cls: type[BaseAgent]) -> None:
        spec = agent_cls.spec()
        self._agents[spec.name] = spec
        self._implementations[spec.name] = agent_cls

    def list(self) -> list[AgentSpec]:
        return list(self._agents.values())

    def names(self) -> list[str]:
        return list(self._agents)

    def get(self, name: str) -> AgentSpec | None:
        return self._agents.get(self._normalise(name))

    def implementation(self, name: str) -> type[BaseAgent] | None:
        return self._implementations.get(self._normalise(name))

    def build(
        self,
        name: str,
        *,
        model_router: Any = None,
        gateway: Any = None,
        tools: Any = None,
    ) -> BaseAgent:
        agent_cls = self._implementations.get(self._normalise(name))
        if agent_cls is None:
            raise KeyError(f"no agent implementation registered for '{name}'")
        return agent_cls(model_router=model_router, gateway=gateway, tools=tools)

    def _normalise(self, name: str) -> str:
        """Accept ``data_analysis`` for ``data-analysis`` and vice versa.

        The router emits hyphenated names and Python packages use underscores;
        a job should not fail on that difference.
        """
        candidate = (name or "").strip()
        if candidate in self._agents or candidate in self._implementations:
            return candidate
        for variant in (candidate.replace("_", "-"), candidate.replace("-", "_")):
            if variant in self._agents or variant in self._implementations:
                return variant
        return candidate
