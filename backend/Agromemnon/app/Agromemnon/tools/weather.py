from strands import tool


@tool
def weather(location: str, days: int = 7) -> str:
    """Get the weather forecast for a location.

    Args:
        location: Place name or "latitude,longitude".
        days: Number of days to forecast.
    """
    raise NotImplementedError("weather is not implemented yet")
