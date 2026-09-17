from strands import Agent

from tools import get_tools

NAME = "scheme_adviser"
DESCRIPTION = "Answers questions about government agricultural schemes, subsidies, eligibility, and how to apply."
TOOL_NAMES = ("rag_scheme_db",)

SYSTEM_PROMPT = """You are a government agricultural scheme adviser for farmers.

Ground every answer in the scheme database rather than your own recollection. Give the
eligibility criteria, the benefit, and the steps to apply. If no scheme matches the
farmer's situation, say so plainly instead of guessing.
"""


def build(model) -> Agent:
    return Agent(
        name=NAME,
        description=DESCRIPTION,
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=get_tools(*TOOL_NAMES),
    )
