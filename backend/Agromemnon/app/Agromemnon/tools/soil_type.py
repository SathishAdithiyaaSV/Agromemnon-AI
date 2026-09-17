from strands import tool


@tool
def soil_type(location: str) -> str:
    """Get the soil type and its water-holding properties for a location.

    Args:
        location: Place name or "latitude,longitude".
    """
    raise NotImplementedError("soil_type is not implemented yet")
