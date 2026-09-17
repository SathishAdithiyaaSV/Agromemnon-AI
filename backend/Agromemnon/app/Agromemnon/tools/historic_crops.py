from strands import tool


@tool
def historic_crops(location: str, season: str = "") -> str:
    """Get crops historically grown in a location and how they yielded.

    Args:
        location: District, taluk, or region name.
        season: Crop season, e.g. "kharif" or "rabi"; omit for all seasons.
    """
    raise NotImplementedError("historic_crops is not implemented yet")
