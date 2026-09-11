"""Domain model role.

For a model fine-tuned on refinery / rotating-equipment material. Optional,
and substitutable by ``reasoning`` (same modality, recorded on the decision).

Important: selecting this role changes *fluency in the vocabulary*, not
authority. Domain-model output is subject to exactly the same evidence and
verification rules as any other model output — a plausible-sounding
maintenance recommendation with no citation still fails verification.
"""

from backend.models.gateway.model_registry import RoleDescriptor

DESCRIPTOR = RoleDescriptor(
    role="domain",
    purpose=(
        "Answering questions phrased in plant and maintenance vocabulary: "
        "vibration signatures, bearing wear, SOP interpretation, failure modes "
        "and turnaround planning."
    ),
    setting="P117_DOMAIN_MODEL",
    modalities=("text",),
    capabilities=("domain_qa", "failure_mode_reasoning", "sop_interpretation"),
    suggested_models=(
        "a locally fine-tuned checkpoint served by the local backend",
    ),
    required_for_demo=False,
    notes=(
        "Fluency is not authority. Output from this role carries no extra trust "
        "and must still cite retrieved evidence to pass verification. Set only "
        "if a genuinely domain-tuned model is served locally; otherwise leave "
        "unset and let the reasoning role handle it."
    ),
)

DESCRIPTORS = (DESCRIPTOR,)

__all__ = ["DESCRIPTOR", "DESCRIPTORS"]
