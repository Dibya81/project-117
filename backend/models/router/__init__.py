"""Router package.

``model_router`` resolves a role to a concrete (provider, model) pair.
``task_classifier`` decides *which* role a task needs, and ``routing_policy``
constrains that choice for the deployment. Keeping the three separate means
the "what role" decision can be unit-tested without a provider, and the
"which model" decision cannot be influenced by prose.
"""

from backend.models.router.model_router import (
    ModelRouter,
    ModelUnavailableError,
    ResolvedModel,
)
from backend.models.router.routing_policy import (
    DEFAULT_LIMITS,
    SUBSTITUTIONS,
    RoleLimits,
    RoutingDecision,
    RoutingPolicy,
    RoutingRefused,
)
from backend.models.router.task_classifier import (
    KNOWN_ROLES,
    Classification,
    classify,
)

__all__ = [
    "DEFAULT_LIMITS",
    "KNOWN_ROLES",
    "SUBSTITUTIONS",
    "Classification",
    "ModelRouter",
    "ModelUnavailableError",
    "ResolvedModel",
    "RoleLimits",
    "RoutingDecision",
    "RoutingPolicy",
    "RoutingRefused",
    "classify",
]
