from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class AppState:
    selected_cities: List[Dict] = field(default_factory=list)
    dpe_filters: List[str] = field(default_factory=list)  # ["A","B",...]
    ges_filters: List[str] = field(default_factory=list)
    surface_min: int = 50
    surface_max: int = 200
    results: Optional[object] = None  # DataFrame
    selected_row_idx: Optional[int] = None
