from strands import Agent

from tools import get_tools

NAME = "crop_agent"
DESCRIPTION = (
    "Advises on crop selection, planning and fertilizer doses using weather, past yields "
    "in the area, mandi prices, and soil test results."
)
TOOL_NAMES = ("rag_scheme_db", "weather", "mandi_price", "historic_crops", "fertilizer_recommendation")

SYSTEM_PROMPT = """You are a crop planning adviser for farmers.

Recommend what to grow and when, using the weather forecast, what has grown well in the
area before, and current mandi prices. Explain the trade-offs behind a recommendation and
name the data you relied on, so the farmer can judge it.

For fertilizer advice you need the farmer's soil test values (N, P, K in kg/ha and organic
carbon as a percentage) from their Soil Health Card. Ask for them rather than guessing —
a fabricated soil reading produces a confident but wrong fertilizer dose.
"""


def build(model) -> Agent:
    return Agent(
        name=NAME,
        description=DESCRIPTION,
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=get_tools(*TOOL_NAMES),
    )
