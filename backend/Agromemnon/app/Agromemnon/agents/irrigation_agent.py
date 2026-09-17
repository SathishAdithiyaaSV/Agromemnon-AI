from strands import Agent

from tools import get_tools

NAME = "irrigation_agent"
DESCRIPTION = "Advises on irrigation timing and water quantity based on the weather forecast and local soil type."
TOOL_NAMES = ("weather", "soil_type")

SYSTEM_PROMPT = """You are an irrigation adviser for farmers.

Work out when to irrigate and how much, from the weather forecast and the soil's
water-holding capacity. Give concrete schedules and quantities, and say when expected
rain makes irrigation unnecessary.
"""


def build(model) -> Agent:
    return Agent(
        name=NAME,
        description=DESCRIPTION,
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=get_tools(*TOOL_NAMES),
    )
