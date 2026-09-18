from strands import tool
from strands_tools.retrieve import retrieve as _bedrock_retrieve
import os

KB_ID ="IY3TP8DVNA"
#KB_ID = os.environ.get("SCHEME_KB_ID", "")
REGION = "us-east-1"


@tool
def rag_scheme_db(query: str, level: str = "", category: str = "") -> str:
    """
    Search the government agricultural scheme database for schemes relevant
    to the farmer's question.

    Args:
        query: The farmer's question or situation, in natural language
               (e.g. "relief for a fisherman lost at sea", "subsidy for drip
               irrigation in Maharashtra").
        level: Optional filter — "State" or "Central". Leave blank to search both.
        category: Optional filter — e.g. "Agriculture,Rural & Environment".
                  Leave blank to search all categories.

    Returns:
        The most relevant scheme excerpts (name, eligibility, benefits,
        application steps, documents needed), to ground the answer in.
    """
    if not KB_ID:
        return "Knowledge base is not configured (SCHEME_KB_ID env var missing)."

    filters = []
    if level:
        filters.append({"equals": {"key": "level", "value": level}})
    if category:
        filters.append({"equals": {"key": "schemeCategory", "value": category}})

    tool_input = {
        "text": query,
        "knowledgeBaseId": KB_ID,
        "region": REGION,
        "numberOfResults": 5,
        "enableMetadata": True,
    }
    if filters:
        tool_input["retrieveFilter"] = filters[0] if len(filters) == 1 else {"andAll": filters}

    tool_use = {
        "toolUseId": "rag_scheme_db_call",
        "input": tool_input,
    }

    res = _bedrock_retrieve(tool_use)
    if isinstance(res, dict) and "content" in res and res["content"]:
        return res["content"][0].get("text", str(res))
    return str(res)

# @tool
# def rag_scheme_db(query: str, top_k: int = 5) -> str:
#     """Search the government agricultural scheme database for schemes matching a query.

#     Args:
#         query: What to look up, e.g. "drip irrigation subsidy for small farmers".
#         top_k: How many matching scheme passages to return.
#     """
#     raise NotImplementedError("rag_scheme_db is not implemented yet")
