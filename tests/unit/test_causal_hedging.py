"""Unit tests for causal claim hedging in data analysis agent."""

import pytest
from backend.agents.data_analysis.hedging import hedge_causal_claims
from backend.agents.data_analysis.agent import DataAnalysisAgent
from backend.agents.base import AgentResult


def test_hedge_causal_claims_direct():
    unhedged = "The temperature spike definitely caused the pump failure and proves that maintenance was neglected."
    hedged, mods = hedge_causal_claims(unhedged)
    assert "is strongly correlated with" in hedged
    assert "suggests that" in hedged
    assert len(mods) == 2


@pytest.mark.asyncio
async def test_data_analysis_agent_postprocess_hedges_claims():
    agent = DataAnalysisAgent()
    raw_result = AgentResult(
        answer=(
            "Analysis of vibration data conclusively proves pump misalignment.\n\n"
            "```python\n"
            "import pandas as pd\n"
            "print({'status': 'ok'})\n"
            "```"
        )
    )

    processed = await agent.postprocess(raw_result, task="Analyze vibration")
    assert "provides evidence of an association with" in processed.answer
    assert processed.code is not None
    assert any("Hedged causal assertion" in note for note in processed.notes)
