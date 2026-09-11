"""Coding model role.

Optional. When unset the router substitutes the more general ``reasoning``
role (same modality) and records the substitution on the routing decision, so
the downgrade is visible in traces rather than silent.

Nothing this role produces is trusted: generated Python only ever runs inside
the sandbox, under the same approval gate as any other ``execute``-risk tool.
"""

from backend.models.gateway.model_registry import RoleDescriptor

DESCRIPTOR = RoleDescriptor(
    role="coding",
    purpose=(
        "Writing the short analysis scripts the sandbox runs, shaping data "
        "transforms, and reading tracebacks when a step fails."
    ),
    setting="P117_CODING_MODEL",
    modalities=("text",),
    capabilities=("code_generation", "code_explanation", "error_diagnosis"),
    suggested_models=(
        "qwen2.5-coder:14b",
        "deepseek-coder-v2:16b",
        "codellama:13b",
    ),
    required_for_demo=False,
    notes=(
        "Generated code is untrusted input, not a trusted plan step. It is "
        "executed only in the sandbox with resource limits and no network, and "
        "never on the API host."
    ),
)

DESCRIPTORS = (DESCRIPTOR,)

__all__ = ["DESCRIPTOR", "DESCRIPTORS"]
