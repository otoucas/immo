## `README.md`

```md
# DPE-GES Finder

Application Streamlit pour interroger les données open data ADEME (DPE/GES) et afficher les résultats (adresse, DPE, GES, surface) sur une **carte** et un **tableau** en permanence. Intégration d’indices DVF (à la même adresse) dans la fiche (popup) de chaque résultat.

## Lancer en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Environnements / configuration

Les URLs d’API sont centralisées dans `config.py`. Adaptez si nécessaire les slugs/URLs des datasets.

```
ADEME_DATASET_SLUG = "dpe-logements-existants-depuis-juillet-2021"
ADEME_API_BASE = "https://data.ademe.fr/data-fair/api/v1"
DVF_DATASET_SLUG = "demandes-de-valeurs-foncieres-geolocalisees"
DVF_API_BASE = "https://www.data.gouv.fr/fr/datasets/r/"  # ou endpoint Data Fair si dispo
ADRESSE_API = "https://api-adresse.data.gouv.fr"  # (service Geoplateforme possible)
```

> Remarque : certains producteurs exposent les données via Data Fair avec des endpoints de type `/datasets/<slug>/lines`. Si l’URL précise change, ne modifier que `config.py`.
```

```

---
