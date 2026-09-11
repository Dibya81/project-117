"""Agent dispatch (Phase 6, consumed by Phase 7).

Owns the one thing that keeps the agent layer from turning into five parallel
half-systems: **agents receive their dependencies, they never build them.**

An agent asked to answer a maintenance question gets the model router, the
tool registry and the already-assembled context pack handed to it. It does not
create an HTTP client, does not choose a model name, and does not call
retrieval itself. That is why there is exactly one place where "which model
serves the reasoning role" is decided, and exactly one place where retrieval
quality can be improved for every agent at once.

The manager also provides the fallback path. If no specialised agent is
registered for a name - which is the state of the system before Phase 7 lands,
and the state of any deployment that disables an agent - the request is
answered directly from the context pack using the reasoning role, with the
same grounded prompt. A missing agent degrades the answer; it does not fail
the job.

The grounded prompt is deliberately blunt about refusing. A local 9B model
will happily produce a plausible torque figure if the prompt does not tell it
that saying "not in these documents" is the correct answer.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

#: Used when no specialised agent is registered for the requested name.
_FALLBACK_SYSTEM = (
    "You are an on-premise industrial documentation assistant. Answer only from the "
    "evidence provided below.\n"
    "Rules:\n"
    "- Cite the bracketed evidence number for every factual claim, e.g. [2].\n"
    "- If the evidence does not contain the answer, say exactly what is missing. "
    "Do not fill the gap from general knowledge.\n"
    "- Never invent page numbers, part numbers, torque values, set points or "
    "procedure steps.\n"
    "- Keep units and tolerances exactly as written in the source."
)


class AgentManager:
    def __init__(
        self,
        registry: Any,
        *,
        model_router: Any = None,
        gateway: Any = None,
        tools: Any = None,
    ) -> None:
        self._registry = registry
        self._model_router = model_router
        self._gateway = gateway
        self._tools = tools

    # --- introspection ----------------------------------------------------

    def names(self) -> list[str]:
        try:
            return [spec.name for spec in self._registry.list()]
        except Exception:  # pragma: no cover - defensive
            return []

    def specs(self) -> list[Any]:
        try:
            return list(self._registry.list())
        except Exception:  # pragma: no cover - defensive
            return []

    # --- dispatch ---------------------------------------------------------

    async def run(
        self,
        *,
        name: str,
        task: str,
        context: Any = None,
        job_id: str | None = None,
        user: str | None = None,
        roles: tuple[str, ...] = (),
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        agent = self._build(name)
        if agent is None:
            logger.info("no specialised agent '%s' registered; answering directly", name)
            return await self._direct_answer(task=task, context=context, agent_name=name)

        result = await agent.execute(
            task=task,
            context=context,
            job_id=job_id,
            user=user,
            roles=roles,
            arguments=dict(arguments or {}),
        )
        if hasattr(result, "to_dict"):
            return result.to_dict()
        return dict(result or {})

    def _build(self, name: str) -> Any | None:
        """Instantiate a specialised agent with injected dependencies.

        Returns ``None`` when the registry has no implementation for the name,
        which is a normal state rather than an error.
        """
        build = getattr(self._registry, "build", None)
        if build is None:
            return None
        try:
            return build(
                name,
                model_router=self._model_router,
                gateway=self._gateway,
                tools=self._tools,
            )
        except KeyError:
            return None
        except Exception:
            logger.warning("agent '%s' failed to initialise", name, exc_info=True)
            return None

    # --- fallback ---------------------------------------------------------

    async def _direct_answer(
        self,
        *,
        task: str,
        context: Any,
        agent_name: str,
    ) -> dict[str, Any]:
        evidence_text = (
            context.prompt_text()
            if context is not None and hasattr(context, "prompt_text")
            else "No evidence was retrieved."
        )
        has_evidence = bool(getattr(context, "has_evidence", False))

        if self._model_router is None or self._gateway is None:
            # Being explicit beats returning an empty string that later looks
            # like a model that had nothing to say.
            return {
                "answer": (
                    "No local model is configured, so no answer could be generated. "
                    "Set the reasoning model role (see .env.example) and retry."
                ),
                "agent": agent_name,
                "model": None,
                "grounded": has_evidence,
                "degraded": True,
            }

        messages = [
            {"role": "system", "content": _FALLBACK_SYSTEM},
            {
                "role": "user",
                "content": f"Evidence:\n{evidence_text}\n\nRequest: {task}",
            },
        ]
        resolved = await self._model_router.resolve("reasoning")
        reply = await self._gateway.chat(model=resolved, messages=messages)
        return {
            "answer": str(getattr(reply, "content", reply) or ""),
            "agent": agent_name,
            "model": getattr(resolved, "model", None),
            "grounded": has_evidence,
            "degraded": True,
        }
