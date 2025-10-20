from typing import List, Tuple
import numpy as np


def centroid(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Retourne (lat, lon) du barycentre d'une liste de points (lat, lon)."""
    if not points:
        return (46.5, 2.5)  # centre France approx
    arr = np.array(points)
    lat = float(arr[:, 0].mean())
    lon = float(arr[:, 1].mean())
    return lat, lon
