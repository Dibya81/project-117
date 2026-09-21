"""Safe evaluation of workflow ``when:`` guards.

A guard is a small expression over the run context, e.g.::

    when: steps.assess.output.severity in ['high', 'critical']
    when: inputs.dry_run == false and steps.fetch.status == 'succeeded'

Implementation note that matters: this does **not** use :func:`eval`. The
expression is parsed with :mod:`ast` and then walked by a small interpreter
that only knows about the node types on the allowlist below. A YAML file is
configuration, and configuration must not be able to execute code -- workflow
definitions may be edited by plant engineers, not just by developers.

Deliberately absent: function calls, arithmetic, comprehensions, lambdas and
attribute access on arbitrary objects. Arithmetic is excluded because ``**``
is a trivial denial-of-service and no guard has needed maths yet; adding it
later is easy, removing an exploit is not.

Path resolution rules:

* Unknown *root* (anything but ``inputs``/``steps``) is an error.
* Unknown *step id* is an error -- that is a definition bug, and silently
  yielding false would make the step vanish without explanation.
* Missing *output key* resolves to ``None`` -- that is data-dependent and a
  legitimate "not present" case.
"""

from __future__ import annotations

import ast
from typing import Any, Mapping, Sequence

ALLOWED_ROOTS: tuple[str, ...] = ("inputs", "steps")

# Author conveniences so YAML can read naturally.
_LITERALS: dict[str, Any] = {
    "true": True,
    "false": False,
    "null": None,
    "none": None,
    "True": True,
    "False": False,
    "None": None,
}

_ALLOWED_NODES: tuple[type, ...] = (
    ast.Expression,
    ast.BoolOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Name,
    ast.Attribute,
    ast.Constant,
    ast.Subscript,
    ast.List,
    ast.Tuple,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Load,
)


class ConditionError(ValueError):
    """The guard could not be parsed or resolved.

    Raised rather than defaulting to false: a broken guard means the author's
    intent is unknown, and guessing would either run something that should not
    have run or silently skip work.
    """

    reason = "condition_invalid"


class _Missing:
    """Marker for an absent output key; renders as None to callers."""

    __slots__ = ()


MISSING = _Missing()


def _check_nodes(tree: ast.AST, expression: str) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ConditionError(
                f"expression uses unsupported syntax "
                f"({type(node).__name__}) in guard: {expression!r}"
            )


def _dotted_path(node: ast.AST) -> list[str] | None:
    """Flatten ``a.b.c`` into ``['a', 'b', 'c']``; None if not a plain path."""
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        parts.reverse()
        return parts
    return None


def _resolve_path(parts: list[str], context: Mapping[str, Any], expression: str) -> Any:
    root = parts[0]
    if root not in ALLOWED_ROOTS:
        raise ConditionError(
            f"guard may only reference {' or '.join(ALLOWED_ROOTS)}, got '{root}' in {expression!r}"
        )
    value: Any = context.get(root) or {}

    if root == "steps":
        if len(parts) < 2:
            raise ConditionError(f"'steps' must be followed by a step id in {expression!r}")
        step_id = parts[1]
        if step_id not in value:
            raise ConditionError(f"guard references unknown step '{step_id}' in {expression!r}")
        value = value[step_id]
        remaining = parts[2:]
    else:
        remaining = parts[1:]

    for part in remaining:
        if part.startswith("__"):
            raise ConditionError(
                f"guard may not reference dunder attribute '{part}' in {expression!r}"
            )
        if isinstance(value, Mapping):
            if part not in value:
                return None  # data-dependent absence
            value = value[part]
        else:
            # Deliberately not getattr(). A guard traverses *data*, not the
            # Python object graph. An attribute fallback would let an
            # expression walk off the end of a step's output into whatever
            # object produced it, which is not something a workflow author
            # was ever offered. A non-mapping has no addressable members.
            return None
    return value


def _evaluate(node: ast.AST, context: Mapping[str, Any], expression: str) -> Any:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, context, expression)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id in _LITERALS:
            return _LITERALS[node.id]
        return _resolve_path([node.id], context, expression)

    if isinstance(node, ast.Attribute):
        parts = _dotted_path(node)
        if parts is None:
            raise ConditionError(f"unsupported attribute access in {expression!r}")
        return _resolve_path(parts, context, expression)

    if isinstance(node, (ast.List, ast.Tuple)):
        return [_evaluate(item, context, expression) for item in node.elts]

    if isinstance(node, ast.Subscript):
        target = _evaluate(node.value, context, expression)
        key = _evaluate(node.slice, context, expression)
        try:
            return target[key]
        except (KeyError, IndexError):
            return None
        except TypeError as exc:
            raise ConditionError(
                f"cannot index {type(target).__name__} in {expression!r}: {exc}"
            ) from exc

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _truthy(_evaluate(node.operand, context, expression))

    if isinstance(node, ast.BoolOp):
        values = node.values
        if isinstance(node.op, ast.And):
            for value in values:
                if not _truthy(_evaluate(value, context, expression)):
                    return False
            return True
        for value in values:
            if _truthy(_evaluate(value, context, expression)):
                return True
        return False

    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, context, expression)
        for op, comparator in zip(node.ops, node.comparators):
            right = _evaluate(comparator, context, expression)
            if not _compare(op, left, right, expression):
                return False
            left = right
        return True

    raise ConditionError(f"unsupported expression node {type(node).__name__} in {expression!r}")


def _compare(op: ast.AST, left: Any, right: Any, expression: str) -> bool:
    try:
        if isinstance(op, ast.Eq):
            return bool(left == right)
        if isinstance(op, ast.NotEq):
            return bool(left != right)
        if isinstance(op, ast.In):
            return _contains(left, right)
        if isinstance(op, ast.NotIn):
            return not _contains(left, right)
        if isinstance(op, ast.Lt):
            return bool(left < right)
        if isinstance(op, ast.LtE):
            return bool(left <= right)
        if isinstance(op, ast.Gt):
            return bool(left > right)
        if isinstance(op, ast.GtE):
            return bool(left >= right)
    except TypeError as exc:
        # Comparing None to a number is almost always a missing-value bug in
        # the definition, so it is reported rather than coerced.
        raise ConditionError(
            f"cannot compare {left!r} with {right!r} in {expression!r}: {exc}"
        ) from exc
    raise ConditionError(f"unsupported comparison in {expression!r}")


def _contains(needle: Any, haystack: Any) -> bool:
    if haystack is None:
        return False
    try:
        return needle in haystack
    except TypeError as exc:
        raise ConditionError(
            f"'in' needs a collection on the right, got {type(haystack).__name__}"
        ) from exc


def _truthy(value: Any) -> bool:
    if isinstance(value, _Missing):
        return False
    return bool(value)


def evaluate(expression: str, context: Mapping[str, Any]) -> bool:
    """Evaluate a guard to a boolean.

    An empty or absent guard is true: "no condition" means "always run".
    """
    if expression is None or not str(expression).strip():
        return True
    text = str(expression).strip()
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ConditionError(f"could not parse guard {text!r}: {exc.msg}") from exc
    _check_nodes(tree, text)
    return _truthy(_evaluate(tree, context, text))


def referenced_steps(expression: str) -> list[str]:
    """Step ids a guard depends on.

    Used at load time to check that a guard only looks at steps that actually
    run before it -- a guard reading a later step's status would always be
    reading an unstarted step.
    """
    if expression is None or not str(expression).strip():
        return []
    try:
        tree = ast.parse(str(expression).strip(), mode="eval")
    except SyntaxError:
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            parts = _dotted_path(node)
            if parts and len(parts) >= 2 and parts[0] == "steps":
                if parts[1] not in found:
                    found.append(parts[1])
    return found


def _collect_paths(node: ast.AST, out: list[list[str]]) -> None:
    """Gather every maximal dotted path in the tree.

    Recursive rather than :func:`ast.walk` because a path must be captured
    whole: walking would also yield ``steps.x`` as an inner node of
    ``steps.x.output`` and report the same reference twice.
    """
    if isinstance(node, (ast.Attribute, ast.Name)):
        parts = _dotted_path(node)
        if parts is not None:
            out.append(parts)
            return
    for child in ast.iter_child_nodes(node):
        _collect_paths(child, out)


def validate_expression(
    expression: str | None,
    *,
    inputs: Sequence[str] | None = None,
    steps: Sequence[str] | None = None,
) -> list[str]:
    """Check a guard's structure without evaluating it.

    Returns a list of human-readable problems; empty means the guard is
    well-formed. This is separate from :func:`evaluate` on purpose. Evaluating
    a guard against placeholder data would report false problems - comparing a
    stand-in ``None`` with a number raises, even though the same guard is fine
    once the step has really run. So load-time validation checks only what is
    knowable statically: syntax, the node allowlist, and whether the names
    referenced exist.

    ``inputs`` and ``steps`` are the declared input keys and the ids of steps
    that run *before* this one. Pass ``None`` (the default) to skip those
    existence checks entirely. An *empty* sequence is not the same thing: it
    asserts that there are no declared inputs, or no prior steps, so any
    reference is an error. That distinction matters for the first step of a
    workflow, where the set of prior steps is legitimately empty and a guard
    referencing any step is a forward reference that can never be true.
    """
    if expression is None or not str(expression).strip():
        return []
    text = str(expression).strip()
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        return [f"could not parse guard {text!r}: {exc.msg}"]

    try:
        _check_nodes(tree, text)
    except ConditionError as exc:
        # A disallowed node makes the rest of the analysis meaningless, so
        # report just this and stop.
        return [str(exc)]

    problems: list[str] = []
    known_inputs = None if inputs is None else set(inputs)
    known_steps = None if steps is None else set(steps)
    paths: list[list[str]] = []
    _collect_paths(tree, paths)

    for parts in paths:
        if len(parts) == 1:
            name = parts[0]
            if name not in _LITERALS:
                problems.append(
                    f"guard {text!r} references bare name '{name}'; only "
                    f"{' or '.join(ALLOWED_ROOTS)} paths and literals are allowed"
                )
            continue
        dunder = [part for part in parts if part.startswith("__")]
        if dunder:
            problems.append(
                f"guard {text!r} references dunder attribute '{dunder[0]}'; "
                "guards may only read declared inputs and step outputs"
            )
            continue
        root = parts[0]
        if root not in ALLOWED_ROOTS:
            problems.append(
                f"guard {text!r} may only reference {' or '.join(ALLOWED_ROOTS)}, got '{root}'"
            )
            continue
        if root == "steps":
            step_id = parts[1]
            if known_steps is not None and step_id not in known_steps:
                problems.append(
                    f"guard {text!r} references step '{step_id}', which does not "
                    "run before this step"
                )
        elif root == "inputs":
            key = parts[1]
            if known_inputs is not None and key not in known_inputs:
                problems.append(f"guard {text!r} references undeclared input '{key}'")
    return problems


__all__ = [
    "ALLOWED_ROOTS",
    "ConditionError",
    "evaluate",
    "referenced_steps",
    "validate_expression",
]
