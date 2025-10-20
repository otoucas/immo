# utils/filters.py
from __future__ import annotations
from typing import Dict, List, Tuple




def active_filters_summary(filters: Dict) -> List[Tuple[str, str]]:
chips: List[Tuple[str, str]] = []
if filters.get("cities"):
chips.append(("cities", "Villes: " + ", ".join(filters["cities"])))
if filters.get("min_surface") is not None:
chips.append(("min_surface", f"Surface min: {filters['min_surface']} m²"))
if filters.get("max_surface") is not None:
chips.append(("max_surface", f"Surface max: {filters['max_surface']} m²"))
return chips




def clear_all_filters(state) -> None:
state.filters = {"cities": [], "min_surface": None, "max_surface": None}




def remove_filter(state, key: str) -> None:
if key in state.filters:
if isinstance(state.filters[key], list):
state.filters[key] = []
else:
state.filters[key] = None
