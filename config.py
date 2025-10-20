from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    # ADEME
    ADEME_API_BASE: str = "https://data.ademe.fr/data-fair/api/v1"
    #ADEME_DATASET_SLUG: str = "dpe-logements-existants-depuis-juillet-2021"
    ADEME_DATASET_SLUG: str = "dpe03existant"

    # DVF (à adapter selon votre source API ; fallback : réutilisation Data.gouv ou service interne)
    # Ex. si dataset exposé via Data Fair : "https://data.gouv.fr/data-fair/api/v1"
    DVF_API_BASE: str = "https://data.ademe.fr/data-fair/api/v1"  # remplacer si besoin
    DVF_DATASET_SLUG: str = "demandes-de-valeurs-foncieres-geolocalisees"  # exemple

    # Géocodage
    ADRESSE_API: str = "https://api-adresse.data.gouv.fr"  # service BAN (toujours actif)
    # Pour Geoplateforme (IGN) : https://geocodage.ign.fr/ (adapter client si vous basculez)

    # App
    MAX_ROWS: int = 1000

SETTINGS = Settings()
