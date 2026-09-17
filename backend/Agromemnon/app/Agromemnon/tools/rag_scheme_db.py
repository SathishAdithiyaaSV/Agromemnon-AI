from strands import tool


@tool
def rag_scheme_db(query: str, top_k: int = 5) -> str:
    """Search the government agricultural scheme database for schemes matching a query.

    Args:
        query: What to look up, e.g. "drip irrigation subsidy for small farmers".
        top_k: How many matching scheme passages to return.
    """
    raise NotImplementedError("rag_scheme_db is not implemented yet")
