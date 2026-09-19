"""Tool registry — every tool lives in its own module in this package.

To add a tool: create `tools/<tool_name>.py` holding one `@tool` function, then
import it below and add it to `ALL_TOOLS`. Any agent can then request it by name.
"""

from tools.fertilizer_recommendation import fertilizer_recommendation
from tools.historic_crops import historic_crops
from tools.leaf_disease import disease_treatment
from tools.mandi_price import mandi_price
from tools.rag_scheme_db import rag_scheme_db
from tools.soil_type import soil_type
from tools.weather import weather
from tools.youtube_search import youtube_search

ALL_TOOLS = [
    disease_treatment,
    fertilizer_recommendation,
    historic_crops,
    mandi_price,
    rag_scheme_db,
    soil_type,
    weather,
    youtube_search,
]

TOOLS_BY_NAME = {tool.tool_name: tool for tool in ALL_TOOLS}


def get_tools(*names: str) -> list:
    """Look up registered tools by name."""
    missing = sorted(set(names) - TOOLS_BY_NAME.keys())
    if missing:
        raise KeyError(f"unregistered tool(s) {missing}; registered: {sorted(TOOLS_BY_NAME)}")
    return [TOOLS_BY_NAME[name] for name in names]
