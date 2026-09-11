"""Data-analysis agent (Phase 7).

This agent does not do arithmetic. It writes the arithmetic down as Python, and
the sandbox does it.

That is the single most important property here. Asked for a mean time between
failures, a language model will produce a number that looks like an answer and
is unverifiable; the same model asked to produce ten lines of pandas produces
something a container can execute, a calculation checker can re-run, and a
reviewer can read. The number then comes from the data, and the model's role is
reduced to choosing the method - which is what it is actually good at.

So :meth:`postprocess` extracts the fenced code block and puts it in
``result.code``. The plan's next step is a ``run_python`` tool call whose
arguments the execution manager fills from this output. The agent never
executes anything: it has no sandbox handle, and ``run_python`` is gated at the
registry as an EXECUTE-risk tool requiring approval.

The prompt constrains the code to the sandbox's real shape: inputs arrive as
files under ``/workspace/inputs``, there is no network, and results must be
printed as JSON so the following step can read them instead of a human
squinting at stdout.
"""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentResult, BaseAgent
from backend.models.providers.base import ChatMessage

#: Mirrors backend.sandbox.service: inputs are written here before execution.
INPUTS_DIR = "/workspace/inputs"

_SYSTEM = (
    "You are a data engineer for an air-gapped industrial analytics system. You do not "
    "state numeric results yourself - you write Python that computes them, and the "
    "sandbox runs it.\n\n"
    "Write a single self-contained Python 3 script. Rules for the script:\n"
    f"- Input files are already present in {INPUTS_DIR}. Read them from there. Do not "
    "download anything: there is no network.\n"
    "- Use only the standard library, pandas, numpy, openpyxl and matplotlib. Nothing "
    "else is installed.\n"
    "- Never call os.system, subprocess, eval, exec, requests or urllib.\n"
    "- Do not write outside /workspace.\n"
    "- Print exactly one JSON object as the last line of output, via "
    "print(json.dumps(result)). Put every computed figure in it, with units in the key "
    "names where they matter.\n"
    "- Guard for the data being different from what you expect: check that columns exist "
    "and report what was found instead of raising.\n"
    "- Show the method, not magic constants: if you filter or resample, make the rule "
    "explicit in a variable.\n\n"
    "Reply in two parts:\n"
    "1. A short paragraph naming the method you chose and its assumptions, citing the "
    "evidence numbers for any threshold or definition you took from the documents.\n"
    "2. One fenced ```python code block containing the whole script.\n\n"
    "Never present a computed value in the prose - the value does not exist until the "
    "sandbox has produced it."
)


class DataAnalysisAgent(BaseAgent):
    name = "data-analysis"
    description = (
        "Designs analyses over uploaded tabular data and writes the Python that computes "
        "them for sandboxed execution, instead of asserting numbers itself."
    )
    capabilities = (
        "design_analysis",
        "write_python_for_sandbox",
        "summarise_computed_results",
        "state_assumptions",
    )
    #: Evidence is useful (definitions, thresholds, limits) but an analysis of
    #: an uploaded CSV is legitimate with no document evidence at all.
    requires_rag = False
    tool_names = ("analyze_csv", "run_python", "search_documents")
    #: The coding role when one is configured; the router falls back to
    #: reasoning only if the deployment maps both roles to the same model.
    model_role = "coding"
    temperature = 0.0
    system_prompt = _SYSTEM

    def build_prompt(
        self,
        *,
        task: str,
        context: Any = None,
        arguments: dict[str, Any] | None = None,
    ) -> list[ChatMessage]:
        arguments = dict(arguments or {})
        files = [str(name) for name in (arguments.get("input_files") or [])][:10]
        listing = (
            "\n".join(f"- {INPUTS_DIR}/{name}" for name in files)
            if files
            else "(no input files were staged; state that the analysis needs data)"
        )
        columns = arguments.get("columns")
        column_hint = f"\nKnown columns: {columns}\n" if columns else ""
        user = (
            f"Input files:\n{listing}\n{column_hint}\n"
            f"Evidence (definitions, thresholds, limits):\n{self.evidence_text(context)}\n\n"
            f"Analysis request: {task}"
        )
        return [
            ChatMessage(role="system", content=self.system_prompt),
            ChatMessage(role="user", content=user[:60_000]),
        ]

    def plan(self, *, task: str, context: Any = None) -> list[dict[str, Any]]:
        """Design, then execute. The second step is a gated tool, not the agent."""
        return [
            {"kind": "agent", "name": self.name, "description": "design the analysis"},
            {
                "kind": "tool",
                "name": "run_python",
                "description": "execute the analysis in the sandbox",
            },
        ]

    async def postprocess(
        self,
        result: AgentResult,
        *,
        task: str,
        context: Any = None,
        arguments: dict[str, Any] | None = None,
    ) -> AgentResult:
        code = self.extract_fenced(result.answer, "python")
        if code is None:
            # No fenced block means no analysis to run. Saying so beats sending
            # prose to an interpreter and reporting a SyntaxError as the
            # analysis result.
            result.degraded = True
            result.notes.append(
                "the model returned no fenced Python block, so there is no analysis to run"
            )
            return result
        result.code = code
        return result
