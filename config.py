## config.py
```python
# config.py
from dataclasses import dataclass

@dataclass
class Settings:
    # ADEME Data Fair dataset slug for DPE logements (change if needed)
    DPE_DATASET_SLUG: str = "dpe-logements"  # e.g., 'dpe-logements' (ADEME Data Fair)

    # Base endpoints
    ADEME_BASE_URL: str = "https://data.ademe.fr/data-fair/api/v1/datasets"
    BAN_SEARCH_URL: str = "https://api-adresse.data.gouv.fr/search/"

    # DVF API (simple, no key). You may replace by a more robust endpoint if available.
    DVF_BASE_URL: str = "https://api.etalab.gouv.fr/api/valeursfoncieres"

    DEFAULT_RESULT_LIMIT: int = 500

settings = Settings()
