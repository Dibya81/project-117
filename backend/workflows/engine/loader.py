from __future__ import annotations

import logging
from pathlib import Path

import yaml

from backend.workflows.engine.registry import WorkflowDefinition, WorkflowRegistry

logger = logging.getLogger(__name__)

#: Workflow definitions that ship with the package, loaded before any
#: deployment directory.
BUILTIN_DEFINITIONS_DIR: Path = Path(__file__).resolve().parent / "definitions"


class WorkflowLoadError(ValueError):
    reason = "workflow_load_error"


def load_workflow_file(path: Path) -> WorkflowDefinition:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise WorkflowLoadError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise WorkflowLoadError(f"{path}: workflow file must contain a mapping at the top level")
    raw.setdefault("name", path.stem)
    try:
        return WorkflowDefinition(**raw, source=str(path))
    except Exception as exc:
        raise WorkflowLoadError(f"{path}: {exc}") from exc


def load_workflows_dir(directory: Path | str) -> list[WorkflowDefinition]:
    directory = Path(directory)
    if not directory.exists():
        logger.info("workflows: directory %s does not exist, nothing to load", directory)
        return []
    definitions: list[WorkflowDefinition] = []
    for path in sorted(directory.rglob("*.yaml")) + sorted(directory.rglob("*.yml")):
        try:
            definitions.append(load_workflow_file(path))
        except WorkflowLoadError as exc:
            logger.warning("workflows: skipping %s: %s", path, exc)
    return definitions


def load_builtin_definitions() -> list[WorkflowDefinition]:
    """Definitions shipped inside the package.

    These exist so a fresh checkout has working workflows without a deployment
    having to author any. They are not samples: they reference only registered
    tools and agents, and they are loaded by the same code path as deployment
    definitions.
    """
    return load_workflows_dir(BUILTIN_DEFINITIONS_DIR)


def load_registry(directory: Path | str, *, include_builtin: bool = True) -> WorkflowRegistry:
    """Build a registry from the built-in pack plus a deployment directory.

    Built-ins load first, then ``directory`` is overlaid. A deployment file
    whose ``name`` matches a built-in **replaces** it, which is the point: a
    site can retune a shipped workflow without editing the package or having
    two workflows answer to the same name. Overrides are logged, because a
    silently shadowed workflow is a bad afternoon.

    Pass ``include_builtin=False`` to load only ``directory`` - used by tests
    that need to assert on an exact set of definitions.
    """
    registry = WorkflowRegistry()
    builtin_names: set[str] = set()

    if include_builtin:
        for definition in load_builtin_definitions():
            registry.register(definition)
            builtin_names.add(definition.name)

    overridden: list[str] = []
    for definition in load_workflows_dir(directory):
        if definition.name in builtin_names:
            overridden.append(definition.name)
        registry.register(definition)

    if overridden:
        logger.info(
            "workflows: deployment definitions override built-in(s): %s",
            ", ".join(sorted(overridden)),
        )
    logger.info(
        "workflows: %d definition(s) available (%d built-in, from %s)",
        len(registry),
        len(builtin_names),
        directory,
    )
    return registry


__all__ = [
    "BUILTIN_DEFINITIONS_DIR",
    "WorkflowLoadError",
    "load_builtin_definitions",
    "load_registry",
    "load_workflow_file",
    "load_workflows_dir",
]
