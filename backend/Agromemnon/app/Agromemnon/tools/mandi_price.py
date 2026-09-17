from strands import tool


@tool
def mandi_price(commodity: str, market: str = "") -> str:
    """Get current mandi prices for a commodity.

    Args:
        commodity: Crop or commodity name, e.g. "onion".
        market: Mandi or market name; omit to cover all nearby markets.
    """
    raise NotImplementedError("mandi_price is not implemented yet")
