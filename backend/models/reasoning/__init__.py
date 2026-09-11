"""Reasoning model role.

Declares what the ``reasoning`` role is for. No model name is bound here: the
concrete model comes from ``P117_REASONING_MODEL`` and is resolved by
``ModelRouter``. ``suggested_models`` is documentation for whoever writes
``.env`` — never a default the code falls back to.
"""

from backend.models.gateway.model_registry import RoleDescriptor

DESCRIPTOR = RoleDescriptor(
    role="reasoning",
    purpose=(
        "Planning, multi-step analysis, synthesis and report drafting. This is "
        "the default role: any task that is not clearly visual, code-shaped or "
        "retrieval-shaped is routed here."
    ),
    setting="P117_REASONING_MODEL",
    modalities=("text",),
    capabilities=("planning", "tool_selection", "summarisation", "drafting"),
    suggested_models=(
        "qwen2.5:14b-instruct",
        "llama3.1:8b-instruct",
        "mistral-small:24b-instruct",
    ),
    required_for_demo=True,
    notes=(
        "The orchestrator cannot produce a plan without this role, so an "
        "unconfigured reasoning model is a startup-visible failure rather than "
        "a surprise halfway through a job."
    ),
)

DESCRIPTORS = (DESCRIPTOR,)

__all__ = ["DESCRIPTOR", "DESCRIPTORS"]
