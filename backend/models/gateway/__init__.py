"""Gateway package.

Canonical implementations live in the modules imported below; this file only
re-exports them. Explicit imports (never ``import *``) so that what the
package offers is readable here and a typo becomes an ImportError at startup
instead of an AttributeError later.
"""

from backend.models.gateway.health_check import (
    HealthChecker,
    ProviderHealth,
)
from backend.models.gateway.load_balancer import (
    LEAST_IN_FLIGHT,
    ROUND_ROBIN,
    STRATEGIES,
    LoadBalancer,
    NoProviderAvailable,
)
from backend.models.gateway.model_gateway import (
    ModelGateway,
)
from backend.models.gateway.model_registry import (
    ROLE_ORDER,
    ModelRegistry,
    RoleDescriptor,
    RoleStatus,
    UnknownRole,
    load_descriptors,
)

__all__ = [
    "LEAST_IN_FLIGHT",
    "ROLE_ORDER",
    "ROUND_ROBIN",
    "STRATEGIES",
    "HealthChecker",
    "LoadBalancer",
    "ModelGateway",
    "ModelRegistry",
    "NoProviderAvailable",
    "ProviderHealth",
    "RoleDescriptor",
    "RoleStatus",
    "UnknownRole",
    "load_descriptors",
]
