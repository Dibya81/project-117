"""Calculation checking (Phase 11).

The review asked for arithmetic to be *recomputed and compared*, not asserted.
This checker finds arithmetic the answer states explicitly and recomputes it.

Two implementation choices are worth stating, because both are load-bearing:

**No ``eval``.** The expressions come from model output built out of document
content, i.e. untrusted text. ``eval("2+2")`` and ``eval("__import__('os')...")``
are the same call. So expressions are tokenised and evaluated by a
shunting-yard implementation over numbers and ``+ - * / %`` only. Anything
that does not tokenise cleanly is skipped rather than guessed at.

**Independence comes from re-derivation, not from a second opinion.** The
checker never asks a model whether the sum is right; it does the sum. That is
what makes it a check rather than a vote. The sandbox is not needed for this -
Python's own arithmetic is already independent of the thing that produced the
claim - and avoiding a container start keeps verification fast enough to run
on every job.

What it recognises:

* ``12 + 5 = 17``, ``480 / 8 = 60``, ``3 * 1.5 = 4.5`` - inline equations.
* ``15% of 240 = 36`` - percentage-of claims, the most common quiet error.
* ``totals to 1,240`` next to a list of numbers is **not** checked; there is no
  reliable way to know which numbers were meant, and a checker that guesses
  produces false FAILEDs, which is the fastest way to get verification
  switched off.

Tolerance: a claim matches if it is within ``1e-6`` relatively, or if it
rounds to the stated value at the precision the answer used - so "33.3%" for
1/3 passes, while "34%" does not.
"""

from __future__ import annotations

import re
import time

from backend.verification.base import CheckResult, CheckStatus, VerificationInput

_NUMBER = r"\d{1,15}(?:,\d{3})*(?:\.\d+)?"

#: ``a op b = c`` with optional further terms, e.g. ``2 + 3 + 4 = 9``.
_EQUATION = re.compile(
    rf"(?<![\w.]) ({_NUMBER} (?:\s*[-+*/%]\s*{_NUMBER})+ ) \s*=\s* ({_NUMBER}) (?![\w.])",
    re.VERBOSE,
)

#: ``15% of 240 is 36`` / ``15 % of 240 = 36``
_PERCENT_OF = re.compile(
    rf"({_NUMBER})\s*%\s*of\s*({_NUMBER})\s*(?:is|=|equals)\s*({_NUMBER})",
    re.IGNORECASE,
)

_TOKEN = re.compile(rf"\s*({_NUMBER}|[-+*/%()])")
_PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2, "%": 2}


class _EvalError(ValueError):
    pass


def _to_float(text: str) -> float:
    return float(text.replace(",", ""))


def _tokenise(expression: str) -> list[str]:
    tokens: list[str] = []
    position = 0
    while position < len(expression):
        match = _TOKEN.match(expression, position)
        if not match:
            if expression[position].isspace():
                position += 1
                continue
            raise _EvalError(f"unexpected character {expression[position]!r}")
        tokens.append(match.group(1))
        position = match.end()
    if not tokens:
        raise _EvalError("empty expression")
    return tokens


def _apply(operator: str, left: float, right: float) -> float:
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/":
        if right == 0:
            raise _EvalError("division by zero")
        return left / right
    if operator == "%":
        if right == 0:
            raise _EvalError("modulo by zero")
        return left % right
    raise _EvalError(f"unsupported operator {operator!r}")


def _evaluate(expression: str) -> float:
    """Evaluate a numeric expression without ``eval``.

    Shunting-yard: numbers to the value stack, operators to the operator
    stack, popping while precedence allows. Left-associative throughout, which
    is correct for the four operators supported.
    """
    values: list[float] = []
    operators: list[str] = []
    expect_value = True

    for token in _tokenise(expression):
        if token in _PRECEDENCE:
            if expect_value:
                if token == "-":  # unary minus
                    values.append(0.0)
                else:
                    raise _EvalError("operator where a number was expected")
            while (
                operators
                and operators[-1] != "("
                and _PRECEDENCE[operators[-1]] >= _PRECEDENCE[token]
            ):
                right = values.pop()
                left = values.pop()
                values.append(_apply(operators.pop(), left, right))
            operators.append(token)
            expect_value = True
        elif token == "(":
            operators.append(token)
            expect_value = True
        elif token == ")":
            while operators and operators[-1] != "(":
                right = values.pop()
                left = values.pop()
                values.append(_apply(operators.pop(), left, right))
            if not operators:
                raise _EvalError("unbalanced parentheses")
            operators.pop()
            expect_value = False
        else:
            values.append(_to_float(token))
            expect_value = False

    while operators:
        operator = operators.pop()
        if operator == "(":
            raise _EvalError("unbalanced parentheses")
        if len(values) < 2:
            raise _EvalError("dangling operator")
        right = values.pop()
        left = values.pop()
        values.append(_apply(operator, left, right))

    if len(values) != 1:
        raise _EvalError("expression did not reduce to a single value")
    return values[0]


def _matches(computed: float, claimed: str) -> bool:
    """Compare allowing for the rounding the answer actually used."""
    value = _to_float(claimed)
    if abs(computed - value) <= max(1e-6, abs(computed) * 1e-6):
        return True
    decimals = len(claimed.split(".")[1]) if "." in claimed else 0
    return round(computed, decimals) == round(value, decimals)


class CalculationChecker:
    name = "calculations"

    async def check(self, payload: VerificationInput) -> CheckResult:
        started = time.perf_counter()
        answer = payload.answer or ""
        findings: list[dict] = []
        checked = 0
        failed = 0

        for match in _EQUATION.finditer(answer):
            expression, claimed = match.group(1), match.group(2)
            try:
                computed = _evaluate(expression)
            except (_EvalError, IndexError, ValueError):
                continue
            checked += 1
            if not _matches(computed, claimed):
                failed += 1
                findings.append(
                    {
                        "type": "arithmetic_mismatch",
                        "expression": expression.strip()[:120],
                        "claimed": claimed,
                        "computed": round(computed, 6),
                    }
                )

        for match in _PERCENT_OF.finditer(answer):
            percent, base, claimed = match.group(1), match.group(2), match.group(3)
            try:
                computed = _to_float(percent) / 100.0 * _to_float(base)
            except ValueError:  # pragma: no cover - regex guarantees numerics
                continue
            checked += 1
            if not _matches(computed, claimed):
                failed += 1
                findings.append(
                    {
                        "type": "percentage_mismatch",
                        "expression": f"{percent}% of {base}",
                        "claimed": claimed,
                        "computed": round(computed, 6),
                    }
                )

        if checked == 0:
            return CheckResult(
                checker=self.name,
                status=CheckStatus.SKIPPED,
                message="the answer states no explicit arithmetic to recompute",
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        status = CheckStatus.FAILED if failed else CheckStatus.PASSED
        message = (
            f"{failed} of {checked} stated calculation(s) do not recompute"
            if failed
            else f"all {checked} stated calculation(s) recompute correctly"
        )
        return CheckResult(
            checker=self.name,
            status=status,
            message=message,
            findings=findings[:25],
            duration_ms=(time.perf_counter() - started) * 1000,
        )
