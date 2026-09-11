"""Action execution gate: policy check → executor → result.

The audit's complaint was that ``execute_plan`` was called directly by the
service, so an "approved action" was just a Python function that mutated the
engine and returned success. This module is the gate in front of it.

Two executor classes, decided by the action itself, not by convenience:

* ``plant_actuator`` — the action is a change to the simulated plant
  (repair an instrument, restore equipment, reduce load). These are actuator
  writes against engine state. They are checked against the operating policy
  below and then executed by the engine, and the engine state is read back
  afterwards: a write that did not take effect is reported ``failed``.
* ``sandbox`` — the action carries a command (``action["command"]``).
  Operator- or model-authored code never runs on the host, so it goes to
  ``backend.sandbox`` under ``SandboxPolicy``. If the sandbox is unavailable
  the action is **blocked** with ``ACTION BLOCKED / SANDBOX UNAVAILABLE`` and
  is never reported as succeeded.

The policy check can and does reject: unknown action kinds, targets that do
not exist in the plant, targets outside the incident scope, and equipment that
an operator has disabled (which requires manual intervention).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from backend.simulation.engine import SimulationEngine
from backend.simulation.models import AssetState, Incident

ALLOWED_KINDS = {"repair_sensor", "restore_equipment", "reduce_load", "sandbox_command"}


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    executor: str  # plant_actuator | sandbox


@dataclass
class ActionOutcome:
    status: str  # completed | blocked | failed
    executor: str
    policy: str  # allowed | blocked
    policy_reason: str
    detail: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.status == "completed"


def check_policy(engine: SimulationEngine, incident: Incident, action: dict) -> PolicyDecision:
    """Operating-policy gate. Denies by default on anything unrecognised."""
    kind = action.get("kind")
    target = action.get("target")
    if kind not in ALLOWED_KINDS:
        return PolicyDecision(False, f"action kind {kind!r} is not permitted", "plant_actuator")
    if action.get("command"):
        return PolicyDecision(True, "command action must run in the sandbox", "sandbox")
    if kind == "sandbox_command":
        return PolicyDecision(False, "sandbox_command requires a command payload", "sandbox")

    scope = {incident.origin_equipment, *incident.affected}
    if kind == "repair_sensor":
        model = engine.sensor_model.get(target)
        if model is None:
            return PolicyDecision(False, f"unknown sensor {target!r}", "plant_actuator")
        if model.equipment_id not in scope:
            return PolicyDecision(False, f"sensor {target!r} is outside the incident scope", "plant_actuator")
        return PolicyDecision(True, "instrument maintenance within incident scope", "plant_actuator")

    if target not in engine.eq:
        return PolicyDecision(False, f"unknown equipment {target!r}", "plant_actuator")
    if target not in scope:
        return PolicyDecision(False, f"equipment {target!r} is outside the incident scope", "plant_actuator")
    if engine.eq[target].state == AssetState.DISABLED:
        return PolicyDecision(False, f"equipment {target!r} is disabled; manual intervention required", "plant_actuator")
    return PolicyDecision(True, "plant actuation within incident scope", "plant_actuator")


class SandboxExecutor:
    """Runs command-bearing actions through the project's sandbox service."""

    def available(self) -> tuple[bool, str]:
        try:
            from backend.sandbox import SandboxPolicy, policy_from_settings  # noqa: F401
        except Exception as exc:
            return False, f"sandbox package unavailable: {exc.__class__.__name__}: {exc}"
        try:
            from backend.core.settings import get_settings

            policy = policy_from_settings(get_settings())
        except Exception as exc:
            return False, f"sandbox policy unavailable: {exc.__class__.__name__}: {exc}"
        try:
            policy.validate_ready()
        except Exception as exc:
            return False, f"sandbox not ready: {exc}"
        return True, "sandbox ready"

    def run(self, command: str, *, job_id: str) -> ActionOutcome:
        ok, why = self.available()
        if not ok:
            return ActionOutcome(
                status="blocked", executor="sandbox", policy="allowed",
                policy_reason="command action requires sandbox",
                detail={"message": "ACTION BLOCKED / SANDBOX UNAVAILABLE", "reason": why},
            )
        from backend.core.settings import get_settings
        from backend.sandbox import OpenSandboxClient, SandboxUnavailable, policy_from_settings

        async def _go() -> dict[str, Any]:
            client = OpenSandboxClient(policy_from_settings(get_settings()))
            async with client.session(job_id=job_id, purpose="python") as session:
                execution = await session.run(command)
                return execution.to_dict() if hasattr(execution, "to_dict") else dict(execution)

        try:
            result = asyncio.run(_go())
        except SandboxUnavailable as exc:
            return ActionOutcome(
                status="blocked", executor="sandbox", policy="allowed",
                policy_reason="command action requires sandbox",
                detail={"message": "ACTION BLOCKED / SANDBOX UNAVAILABLE", "reason": str(exc)},
            )
        except Exception as exc:
            return ActionOutcome(
                status="failed", executor="sandbox", policy="allowed",
                policy_reason="command action requires sandbox",
                detail={"error": f"{exc.__class__.__name__}: {exc}"},
            )
        status = "completed" if result.get("exit_code") in (0, None) else "failed"
        return ActionOutcome(status, "sandbox", "allowed", "command action executed in sandbox", result)


class PlantActuator:
    """Applies an approved change to engine state and reads it back."""

    def run(self, engine: SimulationEngine, action: dict) -> ActionOutcome:
        kind = action["kind"]
        target = action["target"]
        try:
            if kind == "repair_sensor":
                before = engine.sensors[target].quality.value
                engine.repair_sensor(target)
                after = engine.sensors[target].quality.value
                detail = {"executed": kind, "target": target,
                          "quality_before": before, "quality_after": after}
                status = "completed" if not engine.sensors[target].failed else "failed"
            elif kind == "restore_equipment":
                before = engine.eq[target].capacity
                engine.restore_equipment(target)
                rt = engine.eq[target]
                detail = {"executed": kind, "target": target,
                          "capacity_before": before, "capacity_after": rt.capacity,
                          "faults_cleared": not rt.faults}
                status = "completed" if rt.capacity > before or not rt.faults else "failed"
            elif kind == "reduce_load":
                rt = engine.eq[target]
                before = rt.capacity
                rt.capacity = max(0.4, rt.capacity * 0.8)
                detail = {"executed": kind, "target": target,
                          "capacity_before": before, "capacity_after": rt.capacity}
                status = "completed" if rt.capacity <= before else "failed"
            else:
                return ActionOutcome("failed", "plant_actuator", "allowed", "unknown kind", {"error": kind})
        except KeyError as exc:
            return ActionOutcome("failed", "plant_actuator", "allowed", "target missing", {"error": str(exc)})
        return ActionOutcome(status, "plant_actuator", "allowed", "plant actuation", detail)


def execute_action(engine: SimulationEngine, incident: Incident, action: dict, *, job_id: str) -> ActionOutcome:
    """The only path from an approved plan to a state change."""
    decision = check_policy(engine, incident, action)
    if not decision.allowed:
        return ActionOutcome(
            status="blocked", executor=decision.executor, policy="blocked",
            policy_reason=decision.reason,
            detail={"message": "ACTION BLOCKED / POLICY", "reason": decision.reason},
        )
    if decision.executor == "sandbox":
        return SandboxExecutor().run(str(action["command"]), job_id=job_id)
    return PlantActuator().run(engine, action)
